import os
import sys
import re
import json
import logging
import argparse
import fitz  # PyMuPDF
from datetime import datetime
import glob
from pathlib import Path
from typing import Dict, Union, Optional
from PyPDF2 import PdfReader
import subprocess # Importar subprocess

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def normalizar_numero(valor: str) -> float:
    """
    Convierte un string de valor monetario a float.
    Ejemplo: "1,234.56" -> 1234.56
    """
    try:
        # Eliminar símbolos de moneda y espacios
        valor = re.sub(r'[$\\s,]', '', valor)
        # Manejar el caso de números que ya tienen punto decimal pero también comas (ej. "1,234.56")
        # La línea anterior ya elimina las comas, así que solo convertimos a float
        return float(valor)
    except (ValueError, TypeError):
        logging.warning(f"No se pudo convertir el valor '{valor}' a float.")
        return 0.0

def detectar_formato(texto_pdf):
    """
    Detecta el formato del PDF basado en patrones específicos.
    Retorna un identificador de formato.
    """
    # Formato 1: Valores en línea (etiqueta, espacios, número)
    if re.search(r'Prima\\s+neta\\s+\\d', texto_pdf):
        logging.debug("Detectado: FORMATO_LINEAL")
        return "FORMATO_LINEAL"
    
    # Formato 2/3: Etiquetas y valores en líneas separadas (etiqueta, newline, espacios opcionales, número)
    # O el formato vertical específico O_6731931
    if (re.search(r'Prima\\s+neta\\s*\\n\\s*\\d', texto_pdf) or 
        re.search(r'Prima neta\\s*\\nTasa de financiamiento\\s*\\nGastos por expedición\\s*\\nI\\.V\\.A\\.\\s*\\nPrecio total\\s*\\n', texto_pdf, re.MULTILINE)):
        logging.debug("Detectado: FORMATO_VERTICAL")
        return "FORMATO_VERTICAL"
    
    # Formato 4: Con tabla previa de coberturas (puede tener luego formato lineal o vertical)
    # Solo detectamos la presencia de la tabla, la lógica de extracción decidirá después
    if re.search(r'Coberturas\\s+amparadas[\\s\\S]*Suma\\s+asegurada[\\s\\S]*Deducible[\\s\\S]*Prima', texto_pdf):
        logging.debug("Detectado: FORMATO_TABLA (puede ser lineal o vertical después)")
        # Podríamos retornar "FORMATO_TABLA_LINEAL" o "FORMATO_TABLA_VERTICAL" si refinamos más
        # Por ahora, trataremos TABLA como un posible LINEAL o VERTICAL en la lógica principal
        if re.search(r'Prima\\s+neta\\s+\\d', texto_pdf):
             return "FORMATO_LINEAL" # Tabla seguida de formato lineal
        elif re.search(r'Prima\\s+neta\\s*\\n\\s*\\d', texto_pdf):
             return "FORMATO_VERTICAL" # Tabla seguida de formato vertical

    logging.debug("Detectado: FORMATO_DESCONOCIDO")
    return "FORMATO_DESCONOCIDO"

def extraer_desde_texto_crudo(texto_crudo):
    """
    Extrae datos financieros analizando el texto crudo línea por línea.
    Prioriza la búsqueda del formato de bloque vertical (etiquetas -> valores).
    Como fallback, busca etiquetas clave y el valor numérico siguiente.
    """
    prima_neta = None
    tasa_financiamiento = None
    gastos_expedicion = None
    iva = None
    precio_total = None
    
    lineas = texto_crudo.split('\n')
    num_lineas = len(lineas)
    
    try:
        # --- Estrategia 1 (Texto Crudo): Buscar Bloque Vertical Específico --- 
        logging.debug("Texto Crudo - Intentando Estrategia 1: Buscar bloque vertical completo...")
        
        # --- Modificar patrón para capturar Tasa --- 
        patron_bloque_vertical = (
            r'Prima\s+neta\s*\n'
            r'Tasa\s+de\s+financiamiento\s*\n'
            r'Gastos\s+por\s+expedición\s*\n'
            r'I\.V\.A\.\s*\n'
            r'(?:Precio\s+total|Total\s+a\s+pagar)\s*\n'
            r'\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*\n'  # Prima Neta (Grupo 1)
            r'\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*\n'  # Tasa (Grupo 2) <- Ahora capturado
            r'\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*\n'  # Gastos Expedición (Grupo 3)
            r'\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*\n'  # IVA (Grupo 4)
            r'\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*'   # Precio Total (Grupo 5)
        )
        # --- Fin de la modificación ---
                               
        match_bloque = re.search(patron_bloque_vertical, texto_crudo, re.IGNORECASE | re.MULTILINE)
        
        if match_bloque:
            logging.info("Texto Crudo - Encontrado bloque vertical completo.")
            # --- Ajustar índices de grupo --- 
            prima_neta = normalizar_numero(match_bloque.group(1))
            tasa_financiamiento = normalizar_numero(match_bloque.group(2)) # Asignar tasa
            gastos_expedicion = normalizar_numero(match_bloque.group(3))
            iva = normalizar_numero(match_bloque.group(4))
            precio_total = normalizar_numero(match_bloque.group(5))
            # --- Fin ajuste índices --- 
            logging.info(f"Texto Crudo - Valores del bloque: PN={prima_neta}, TF={tasa_financiamiento}, GE={gastos_expedicion}, IVA={iva}, PT={precio_total}")
        else:
            # --- Inicio del bloque else (Fallback) --- 
            logging.info("Texto Crudo - No se encontró el bloque vertical completo. Intentando Estrategia 2 (búsqueda por etiqueta individual)...")
            campos_a_buscar = {
                'prima_neta': {'etiqueta': r'Prima\s+neta', 'valor': None},
                'tasa_financiamiento': {'etiqueta': r'Tasa\s+de\s+financiamiento', 'valor': None},
                'gastos_expedicion': {'etiqueta': r'Gastos\s+por\s+expedición', 'valor': None},
                'iva': {'etiqueta': r'I\.V\.A\.', 'valor': None},
                'precio_total': {'etiqueta': r'Precio\s+total|Total\s+a\s+pagar', 'valor': None}
            }
            
            # Iterar sobre los campos que queremos encontrar (Fallback)
            for campo, data in campos_a_buscar.items():
                logging.debug(f"Texto Crudo/Fallback - Buscando etiqueta para: {campo} (Patrón: {data['etiqueta']})")
                etiqueta_encontrada_idx = -1
                
                # Buscar la línea donde aparece la etiqueta
                for i, linea in enumerate(lineas):
                    if re.search(data['etiqueta'], linea, re.IGNORECASE):
                        logging.debug(f"Texto Crudo/Fallback - Etiqueta para '{campo}' encontrada en línea {i+1}: '{linea.strip()}'")
                        etiqueta_encontrada_idx = i
                        break # Encontramos la primera ocurrencia
                
                # Si encontramos la etiqueta, buscar el primer número en las líneas siguientes
                if etiqueta_encontrada_idx != -1:
                    for j in range(1, 6): # Buscar en las próximas 5 líneas
                        idx_valor = etiqueta_encontrada_idx + j
                        if idx_valor < num_lineas:
                            linea_valor = lineas[idx_valor].strip()
                            numero_match = re.search(r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', linea_valor)
                            if numero_match:
                                valor_str = numero_match.group(1)
                                # Evitar asignar el mismo valor a múltiples campos si ya tiene uno
                                if campos_a_buscar[campo]['valor'] is None:
                                     campos_a_buscar[campo]['valor'] = normalizar_numero(valor_str)
                                     logging.info(f"Texto Crudo/Fallback - Encontrado valor para '{campo}': {valor_str} en línea {idx_valor + 1}")
                                     break 
                            # Seguir buscando en las siguientes líneas incluso si no hay número
                        else:
                            logging.debug(f"Texto Crudo/Fallback - Fin del archivo alcanzado buscando valor para '{campo}'")
                            break
                else:
                    logging.warning(f"Texto Crudo/Fallback - No se encontró la etiqueta para: {campo}")

            # Asignar valores encontrados desde el fallback (si no se encontraron con el bloque)
            if not prima_neta: prima_neta = campos_a_buscar['prima_neta'].get('valor')
            if not tasa_financiamiento: tasa_financiamiento = campos_a_buscar['tasa_financiamiento'].get('valor')
            if not gastos_expedicion: gastos_expedicion = campos_a_buscar['gastos_expedicion'].get('valor')
            if not iva: iva = campos_a_buscar['iva'].get('valor')
            if not precio_total: precio_total = campos_a_buscar['precio_total'].get('valor')

    except Exception as e:
        logging.error(f"Error procesando texto crudo: {e}", exc_info=True)
        return None

    # --- Modificar verificación y retorno --- 
    # Ahora verificamos todos los campos EXCEPTO tasa, que es opcional en el sentido
    # de que solo la estrategia del bloque vertical la extrae actualmente.
    valores_principales_ok = all([prima_neta is not None, gastos_expedicion is not None, iva is not None, precio_total is not None])
    
    if valores_principales_ok:
        logging.info("Texto Crudo - Valores principales extraídos exitosamente.")
        return {
            'prima_neta': prima_neta,
            'tasa_financiamiento': tasa_financiamiento, # Incluir tasa (puede ser None)
            'gastos_expedicion': gastos_expedicion,
            'iva': iva,
            'precio_total': precio_total
        }
    else:
        logging.warning("Texto Crudo - No se lograron extraer todos los valores principales requeridos.")
        return None
    # --- Fin modificación --- 

def extraer_datos_endoso_a(pdf_path):
    """
    Extrae los datos financieros de un PDF de tipo A.
    Versión mejorada con múltiples estrategias.
    """
    logging.info(f"Procesando archivo: {pdf_path}")
    try:
        reader = PdfReader(pdf_path)
        if len(reader.pages) < 1:
            logging.error(f"El PDF {pdf_path} no tiene páginas")
            return None
            
        # Extraer texto SOLO de la primera página
        texto_pdf = reader.pages[0].extract_text()
        logging.debug(f"Texto extraído (primeros 500 chars): {texto_pdf[:500]}")

        formato = detectar_formato(texto_pdf)
        logging.info(f"Formato detectado: {formato}")
            
        prima_neta = None
        tasa_financiamiento = None
        gastos_expedicion = None
        iva = None
        precio_total = None
        
        # --- Estrategia 1: Patrones específicos por formato ---
        logging.info("Intentando Estrategia 1: Patrones específicos por formato...")
        
        # Definir patrones base
        patrones_base = {
            'prima_neta': r'Prima\s+neta',
            'gastos_expedicion': r'Gastos\s+por\s+expedición',
            'iva': r'I\.V\.A\.',
            'precio_total': r'Precio\s+total|Total\s+a\s+pagar' # Incluir alternativa común
        }
        
        # Construir patrones específicos según el formato
        patrones_especificos = {}
        if formato == "FORMATO_LINEAL":
            # Etiqueta seguido de espacios y número en la misma línea
            for k, v in patrones_base.items():
                patrones_especificos[k] = [f'{v}\\s+(\\d{{1,3}}(?:,\\d{{3}})*(?:\\.\\d{{2}})?)\\b']
        elif formato == "FORMATO_VERTICAL":
            # Etiqueta seguido de newline (con o sin espacios) y número
             for k, v in patrones_base.items():
                 # Priorizar patrón con valor en la línea siguiente inmediata
                 p1 = f'{v}\\s*\\n\\s*(\\d{{1,3}}(?:,\\d{{3}})*(?:\\.\\d{{2}})?)\\b'
                 # Patrón para bloque O_6731931 (ya no necesario aquí si se maneja aparte, pero como fallback)
                 p2 = f'{v}\\s*\\n([\\d\\.,]+)' # Menos específico
                 patrones_especificos[k] = [p1, p2]
             # Patrón específico para el bloque completo O_6731931
             patron_bloque_vertical = r'Prima neta\\s*\\nTasa de financiamiento\\s*\\nGastos por expedición\\s*\\nI\\.V\\.A\\.\\s*\\nPrecio total\\s*\\n(\\d{1,3}(?:,\\d{3})*(?:\\.\\d{2})?)\\s*\\n(?:\\d{1,3}(?:,\\d{3})*(?:\\.\\d{2})?)\\s*\\n(\\d{1,3}(?:,\\d{3})*(?:\\.\\d{2})?)\\s*\\n(\\d{1,3}(?:,\\d{3})*(?:\\.\\d{2})?)\\s*\\n(\\d{1,3}(?:,\\d{3})*(?:\\.\\d{2})?)'

        else: # FORMATO_DESCONOCIDO o FORMATO_TABLA (tratar genéricamente)
             # Intentar ambos patrones (lineal y vertical) más uno genérico
             for k, v in patrones_base.items():
                patrones_especificos[k] = [
                    f'{v}\\s+(\\d{{1,3}}(?:,\\d{{3}})*(?:\\.\\d{{2}})?)\\b', # Lineal
                    f'{v}\\s*\\n\\s*(\\d{{1,3}}(?:,\\d{{3}})*(?:\\.\\d{{2}})?)\\b', # Vertical
                    f'{v}[\\s\\n]*?(\\d{{1,3}}(?:,\\d{{3}})*(?:\\.\\d{{2}})?)\\b' # Genérico
                ]
        
        # Aplicar patrones específicos
        datos_temp = {}
        for campo, lista_patrones in patrones_especificos.items():
             for i, patron in enumerate(lista_patrones):
                 match = re.search(patron, texto_pdf)
                 if match:
                    valor_str = match.group(1)
                    datos_temp[campo] = normalizar_numero(valor_str)
                    logging.info(f"Estrategia 1 - Encontrado {campo}: {valor_str} usando patrón #{i+1}: {patron}")
                    break # Pasar al siguiente campo si se encontró

        prima_neta = datos_temp.get('prima_neta')
        gastos_expedicion = datos_temp.get('gastos_expedicion')
        iva = datos_temp.get('iva')
        precio_total = datos_temp.get('precio_total')

        # Intentar con el patrón de bloque vertical si es FORMATO_VERTICAL y no se encontraron todos
        if formato == "FORMATO_VERTICAL" and not all([prima_neta, gastos_expedicion, iva, precio_total]):
             logging.info("Intentando Estrategia 1b: Patrón de bloque vertical específico...")
             match_bloque = re.search(patron_bloque_vertical, texto_pdf, re.MULTILINE)
             if match_bloque:
                 logging.info("Encontrado patrón de bloque vertical.")
                 # Asignar solo si no se encontraron previamente
                 if not prima_neta: prima_neta = normalizar_numero(match_bloque.group(1))
                 if not gastos_expedicion: gastos_expedicion = normalizar_numero(match_bloque.group(2))
                 if not iva: iva = normalizar_numero(match_bloque.group(3))
                 if not precio_total: precio_total = normalizar_numero(match_bloque.group(4))
                 logging.info(f"Valores del bloque: PN={match_bloque.group(1)}, GE={match_bloque.group(2)}, IVA={match_bloque.group(3)}, PT={match_bloque.group(4)}")


        # --- Estrategia 2: Patrones Genéricos (si Estrategia 1 falló) ---
        if not all([prima_neta, gastos_expedicion, iva, precio_total]):
            logging.info("Intentando Estrategia 2: Patrones genéricos...")
            patrones_genericos = {
                 'prima_neta': r'Prima\s+neta[\s\n]*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\b',
                 'tasa_financiamiento': r'Tasa\s+de\s+financiamiento[\s\n]*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\b',
                 'gastos_expedicion': r'Gastos\s+por\s+expedición[\s\n]*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\b',
                 'iva': r'I\.V\.A\.[\s\n]*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\b',
                 'precio_total': r'(?:Precio\s+total|Total\s+a\s+pagar)[\s\n]*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\b'
            }
            datos_temp_gen = {}
            for campo, patron in patrones_genericos.items():
                 match = re.search(patron, texto_pdf)
                 if match:
                     valor_str = match.group(1)
                     datos_temp_gen[campo] = normalizar_numero(valor_str)
                     logging.info(f"Estrategia 2 - Encontrado {campo}: {valor_str} usando patrón: {patron}")

            # Asignar solo si no se encontraron previamente
            if not prima_neta: prima_neta = datos_temp_gen.get('prima_neta')
            if not tasa_financiamiento: tasa_financiamiento = datos_temp_gen.get('tasa_financiamiento')
            if not gastos_expedicion: gastos_expedicion = datos_temp_gen.get('gastos_expedicion')
            if not iva: iva = datos_temp_gen.get('iva')
            if not precio_total: precio_total = datos_temp_gen.get('precio_total')


        # --- Estrategia 3: Texto Crudo (pdftotext -raw) ---
        if not all([prima_neta, gastos_expedicion, iva, precio_total]):
            logging.info("Intentando Estrategia 3: Texto crudo (pdftotext -raw)...")
            try:
                result = subprocess.run(['pdftotext', '-raw', pdf_path, '-'], capture_output=True, text=True, check=True)
                texto_crudo = result.stdout
                logging.debug(f"Texto crudo obtenido (primeros 500 chars): {texto_crudo[:500]}")
                resultado_crudo = extraer_desde_texto_crudo(texto_crudo)
                if resultado_crudo:
                    logging.info("Valores encontrados desde texto crudo.")
                    # Asignar solo si no se encontraron previamente
                    if not prima_neta: prima_neta = resultado_crudo.get('prima_neta')
                    if not tasa_financiamiento: tasa_financiamiento = resultado_crudo.get('tasa_financiamiento') # Obtener TASA
                    if not gastos_expedicion: gastos_expedicion = resultado_crudo.get('gastos_expedicion')
                    if not iva: iva = resultado_crudo.get('iva')
                    if not precio_total: precio_total = resultado_crudo.get('precio_total')
                else:
                    logging.warning("No se encontraron valores desde texto crudo.")
            except FileNotFoundError:
                 logging.error("Comando 'pdftotext' no encontrado. Asegúrate de que esté instalado y en el PATH.")
            except subprocess.CalledProcessError as e:
                 logging.error(f"Error al ejecutar pdftotext: {e}")
            except Exception as e:
                logging.error(f"Error inesperado al procesar texto crudo: {str(e)}")

        # --- Estrategia 4: Sumar Primas Individuales (Fallback para prima_neta) ---
        if not prima_neta:
             logging.info("Intentando Estrategia 4: Sumar primas individuales...")
             # Busca una línea que empiece con "Prima" y tenga varios números después
             prima_section_match = re.search(r'^Prima\\s+(\\d{1,3}(?:,\\d{3})*(?:\\.\\d{2})?(?:\\s+\\d{1,3}(?:,\\d{3})*(?:\\.\\d{2})?)*)', texto_pdf, re.MULTILINE)
             if prima_section_match:
                 numeros_primas = re.findall(r'(\\d{1,3}(?:,\\d{3})*(?:\\.\\d{2})?)', prima_section_match.group(1))
                 if numeros_primas:
                     suma_primas = sum(normalizar_numero(n) for n in numeros_primas)
                     prima_neta = suma_primas
                     logging.info(f"Estrategia 4 - Encontrado prima_neta (suma de primas): {prima_neta}")
                 else:
                     logging.warning("Estrategia 4 - Se encontró línea de Prima pero no números.")
             else:
                  logging.warning("Estrategia 4 - No se encontró la sección de primas individuales.")


        # --- Verificación Final (modificada) --- 
        logging.info(f"Resultados finales de extracción: PN={prima_neta}, TF={tasa_financiamiento}, GE={gastos_expedicion}, IVA={iva}, PT={precio_total}")
        # Consideramos la extracción exitosa si tenemos los 4 valores principales.
        # Tasa de financiamiento es opcional en este punto.
        valores_principales_ok = all([prima_neta is not None, gastos_expedicion is not None, iva is not None, precio_total is not None])

        if not valores_principales_ok:
            # Log detallado de qué faltó de los principales
            faltantes = []
            if prima_neta is None: faltantes.append("Prima Neta")
            if gastos_expedicion is None: faltantes.append("Gastos Expedición")
            if iva is None: faltantes.append("IVA")
            if precio_total is None: faltantes.append("Precio Total")
            logging.error(f"No se encontraron todos los valores principales requeridos. Faltantes: {', '.join(faltantes)}")
            return None
        
        logging.info("Todos los valores principales requeridos fueron extraídos.")
        return {
            'prima_neta': prima_neta,
            'tasa_financiamiento': tasa_financiamiento, # Incluir tasa (puede ser None)
            'gastos_expedicion': gastos_expedicion,
            'iva': iva,
            'precio_total': precio_total,
            'ramo': 'AUTOS', 
            'tipo_endoso': 'A - MODIFICACIÓN DE DATOS'
        }
        
    except Exception as e:
        logging.error(f"Error fatal al procesar el archivo {pdf_path}: {str(e)}", exc_info=True) # Log con traceback
        return None

def extract_endoso_b_data(text, pdf_path):
    """Extrae datos específicos para endosos tipo B."""
    data = {}
    
    # Extraer número de póliza
    poliza_match = re.search(r'Póliza\s+(\d+)', text)
    if poliza_match:
        data["Número de póliza"] = poliza_match.group(1)
    
    # Extraer número de endoso
    endoso_match = re.search(r'Endoso\s+([A-Z0-9]+)', text)
    if endoso_match:
        data["Número de endoso"] = endoso_match.group(1)
    
    # Extraer vigencia
    vigencia_desde = re.search(r'Desde:\s+(\d{2}/\w{3}/\d{4})', text)
    vigencia_hasta = re.search(r'Hasta:\s+(\d{2}/\w{3}/\d{4})', text)
    if vigencia_desde:
        data["Vigencia desde"] = vigencia_desde.group(1)
    if vigencia_hasta:
        data["Vigencia hasta"] = vigencia_hasta.group(1)
    
    # Extraer datos del asegurado
    nombre_match = re.search(r'Nombre:\s+(.*?)(?:\s{3}|$)', text, re.DOTALL)
    if nombre_match:
        data["Nombre del asegurado"] = nombre_match.group(1).strip()
    
    # Extraer datos del vehículo
    vehiculo_match = re.search(r'Vehículo:\s+(.*?)(?:\s+Motor:|$)', text, re.DOTALL)
    if vehiculo_match:
        data["Vehículo"] = vehiculo_match.group(1).strip()
    
    # Extraer placa
    placa_match = re.search(r'Placas:\s+([A-Z0-9]+)', text)
    if placa_match:
        data["Placas"] = placa_match.group(1)
    
    # Extraer modelo
    modelo_match = re.search(r'Modelo:\s+(\d{4})', text)
    if modelo_match:
        data["Modelo"] = modelo_match.group(1)
    
    # Tipo de endoso (extraer de la descripción o del nombre del archivo)
    filename = os.path.basename(pdf_path)
    # Intentar extraer el tipo de endoso del nombre del archivo (ej: CAMBIO, CANCELACION)
    tipo_endoso_match = re.search(r'AUTOS/([A-Z]+)/', filename)
    if tipo_endoso_match:
        data["Tipo de endoso"] = tipo_endoso_match.group(1)
    
    # Extraer descripción del cambio
    descripcion_match = re.search(r'Se hace constar que, (.*?)(?:$|\n\n)', text, re.DOTALL)
    if descripcion_match:
        data["Descripción del cambio"] = descripcion_match.group(1).strip()
    
    # Si no hay datos financieros, indicar el motivo
    data["Nota"] = "Este es un endoso tipo B que no contiene información financiera"
    
    return data

def extract_traditional_format(text):
    """Extrae datos financieros del formato tradicional (columna de datos)"""
    logging.info("Detectado formato tradicional (columna de datos)")
    
    # Normalizar el texto: reemplazar múltiples espacios y saltos de línea con un solo espacio
    text = re.sub(r'\s+', ' ', text)
    
    # Buscar el bloque de valores financieros
    # Primero encontrar las etiquetas
    labels_pattern = r"Prima neta\s*Tasa de financiamiento\s*Gastos por expedición\s*I\.V\.A\.\s*Precio total"
    labels_match = re.search(labels_pattern, text, re.IGNORECASE)
    
    if labels_match:
        # Si encontramos las etiquetas, buscar los valores que siguen
        values_text = text[labels_match.end():]
        values_pattern = r"\s*([\d,.]+)\s*([\d,.]+)\s*([\d,.]+)\s*([\d,.]+)\s*([\d,.]+)"
        values_match = re.search(values_pattern, values_text)
        
        if values_match:
            logging.info("Encontrado bloque de valores financieros")
            result = {
                "Prima neta": normalizar_numero(values_match.group(1)),
                "Tasa de financiamiento": normalizar_numero(values_match.group(2)),
                "Gastos por expedición": normalizar_numero(values_match.group(3)),
                "I.V.A.": normalizar_numero(values_match.group(4)),
                "Precio total": normalizar_numero(values_match.group(5))
            }
            
            # Registrar los valores encontrados
            for key, value in result.items():
                logging.info(f"Encontrado {key}: {value}")
            
            return result
    
    # Si no se encuentra el bloque completo, intentar buscar valores individuales
    logging.info("No se encontró el bloque completo, buscando valores individuales")
    result = {}
    
    # Buscar las etiquetas y sus valores correspondientes
    patterns = [
        (r"Prima neta\s*([\d,.]+)", "Prima neta"),
        (r"Tasa de financiamiento\s*([\d,.]+)", "Tasa de financiamiento"),
        (r"Gastos por expedición\s*([\d,.]+)", "Gastos por expedición"),
        (r"I\.V\.A\.\s*([\d,.]+)", "I.V.A."),
        (r"Precio total\s*([\d,.]+)", "Precio total")
    ]
    
    # Buscar cada patrón en el texto
    for pattern, key in patterns:
        # Buscar todas las coincidencias
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if matches:
            # Tomar el último valor encontrado (suele ser el más relevante)
            value = normalizar_numero(matches[-1].group(1))
            result[key] = value
            logging.info(f"Encontrado {key}: {value}")
        else:
            # Si no se encuentra, intentar buscar el valor después de la etiqueta
            label_match = re.search(key, text, re.IGNORECASE)
            if label_match:
                # Buscar el siguiente número después de la etiqueta
                value_match = re.search(r"([\d,.]+)", text[label_match.end():label_match.end()+50])
                if value_match:
                    value = normalizar_numero(value_match.group(1))
                    result[key] = value
                    logging.info(f"Encontrado {key}: {value}")
                else:
                    logging.warning(f"No se encontró valor para {key}")
            else:
                logging.warning(f"No se encontró {key}")
    
    return result if result else None

def extract_generic_format(text):
    """Intenta extraer datos financieros usando patrones genéricos."""
    data = {}
    
    # Intentar extraer valores usando patrones más flexibles
    prima_neta_match = re.search(r'(?:Prima|PRIMA)[^\d]+([\d,.]+)', text)
    if prima_neta_match:
        data["Prima neta"] = normalizar_numero(prima_neta_match.group(1))
    
    tasa_match = re.search(r'(?:Tasa|TASA)[^\d]+([\d,.]+)', text)
    if tasa_match:
        data["Tasa de financiamiento"] = normalizar_numero(tasa_match.group(1))
    
    gastos_match = re.search(r'(?:Gastos|GASTOS)[^\d]+([\d,.]+)', text)
    if gastos_match:
        data["Gastos por expedición"] = normalizar_numero(gastos_match.group(1))
    
    iva_match = re.search(r'(?:I\.V\.A\.|IVA)[^\d]+([\d,.]+)', text)
    if iva_match:
        data["I.V.A."] = normalizar_numero(iva_match.group(1))
    
    precio_match = re.search(r'(?:Precio|PRECIO|Total|TOTAL)[^\d]+([\d,.]+)', text)
    if precio_match:
        data["Precio total"] = normalizar_numero(precio_match.group(1))
    
    return data

def save_to_json(data, output_path):
    """Guarda los datos en formato JSON."""
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        # Filtrar solo los datos extraídos exitosamente antes de guardar
        datos_validos = [d for d in data if d is not None] # Asumiendo que data es una lista de resultados
        with open(output_path, 'w', encoding='utf-8') as f:
             # La función test_endosos.py ahora maneja la estructura del JSON final
             # json.dump(datos_validos, f, ensure_ascii=False, indent=4) # Guardar la lista filtrada
             # Esta función save_to_json parece no usarse directamente en el flujo actual
             # test_endosos.py guarda el JSON él mismo. Se puede eliminar si no se usa en otro lugar.
             pass # Dejarla vacía o eliminar si test_endosos la maneja
        # logging.info(f"Datos guardados en: {output_path}") # Mover log a test_endosos.py
        return True
    except Exception as e:
        logging.error(f"Error al guardar el archivo JSON {output_path}: {str(e)}")
        return False

def create_markdown_table(data, output_path):
    """Crea una tabla en formato Markdown con los datos financieros."""
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Crear encabezado de la tabla
        table = "| Campo | Valor |\n"
        table += "|-------|-------|\n"
        
        # Añadir filas con los datos
        for key, value in data.items():
            table += f"| {key} | {value} |\n"
        
        # Guardar la tabla en un archivo
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(table)
        
        logging.info(f"Tabla de datos financieros añadida al final del archivo")
        return True
    except Exception as e:
        logging.error(f"Error al crear tabla Markdown {output_path}: {str(e)}")
        return False

def create_summary(results, output_md="resumen_financiero.md", output_json="resumen_financiero.json"):
    """Crea un archivo de resumen con todos los resultados."""
    try:
        # Crear tabla de resumen en Markdown
        with open(output_md, 'w', encoding='utf-8') as f:
            f.write("# Resumen Financiero de Pólizas\n\n")
            
            # Encabezado de la tabla
            headers = ["Póliza"]
            if results:
                first_result = next(iter(results.values()))
                headers.extend(first_result.keys())
            
            f.write("| " + " | ".join(headers) + " |\n")
            f.write("|" + "---|" * len(headers) + "\n")
            
            # Filas con datos
            for pdf_name, data in results.items():
                row = [pdf_name]
                for header in headers[1:]:
                    row.append(data.get(header, ""))
                f.write("| " + " | ".join(str(cell) for cell in row) + " |\n")
        
        # Guardar también en formato JSON
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logging.info(f"Resumen creado en: {output_md}")
        logging.info(f"Resumen guardado en: {output_json}")
        return True
    except Exception as e:
        logging.error(f"Error al crear el resumen: {str(e)}")
        return False

def process_single_file(pdf_path, base_output_dir="output"):
    """Procesa un único archivo PDF."""
    # Extraer los datos financieros
    data = extraer_datos_endoso_a(pdf_path)
    
    # Crear nombre de archivo de salida
    basename = os.path.basename(pdf_path)
    output_json = os.path.join(base_output_dir, f"{basename.split('.')[0]}.json")
    output_md = os.path.join(base_output_dir, f"{basename.split('.')[0]}.md")
    
    # Guardar los datos extraídos
    save_to_json(data, output_json)
    create_markdown_table(data, output_md)
    
    return data

def process_directory(directory, base_output_dir="output"):
    """Procesa todos los PDFs en un directorio."""
    results = {}
    
    # Buscar todos los archivos PDF en el directorio
    pdf_files = glob.glob(os.path.join(directory, "*.pdf"))
    logging.info(f"Encontrados {len(pdf_files)} archivos PDF en el directorio {directory}")
    
    for pdf_file in pdf_files:
        logging.info(f"Procesando {pdf_file}...")
        data = process_single_file(pdf_file, base_output_dir)
        results[os.path.basename(pdf_file)] = data
    
    # Crear resumen
    create_summary(results)
    
    return results

def main():
    parser = argparse.ArgumentParser(description='Extrae datos financieros de PDFs de pólizas.')
    parser.add_argument('input', help='Ruta al archivo PDF o directorio con PDFs')
    parser.add_argument('--dir', action='store_true', help='Indica que la entrada es un directorio')
    parser.add_argument('--output', default='output', help='Directorio de salida')
    parser.add_argument('--json', action='store_true', help='Guardar resultados en formato JSON')
    
    args = parser.parse_args()
    
    # Crear directorio de salida si no existe
    os.makedirs(args.output, exist_ok=True)
    
    if args.dir:
        # Procesar todos los PDFs en el directorio
        process_directory(args.input, args.output)
    else:
        # Lista para almacenar múltiples archivos si se proporcionan
        pdf_files = []
        
        # Comprobar si es un patrón glob
        if '*' in args.input:
            pdf_files = glob.glob(args.input)
        else:
            # Comprobar si es un directorio (aunque no se haya especificado --dir)
            if os.path.isdir(args.input):
                logging.warning(f"{args.input} es un directorio. Considerando usar --dir para procesar todos los PDFs.")
                pdf_files = [args.input]
            else:
                # Tratar como una lista de archivos separados por espacios
                pdf_files = args.input.split()
        
        # Procesar cada archivo
        results = {}
        for pdf_file in pdf_files:
            data = process_single_file(pdf_file, args.output)
            results[os.path.basename(pdf_file)] = data
        
        # Crear resumen si hay más de un archivo
        if len(pdf_files) > 1:
            create_summary(results)
    
    logging.info("Proceso completado")

if __name__ == "__main__":
    main()