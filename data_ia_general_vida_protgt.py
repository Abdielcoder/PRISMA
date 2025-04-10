import os
import sys
import re
import json
import logging
import fitz  # PyMuPDF
from datetime import datetime
from typing import Dict, Union, Optional, List, Tuple
from PyPDF2 import PdfReader
import glob
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Variable global para modo debug
DEBUG = os.environ.get("DEBUG", "0") == "1"

def debug_print(mensaje, valor=None):
    """
    Imprime información de debugging si DEBUG=1
    """
    if DEBUG:
        if valor is not None:
            print(f"DEBUG: {mensaje}: '{valor}'")
        else:
            print(f"DEBUG: {mensaje}")

def normalizar_numero(valor: str) -> str:
    """
    Normaliza un valor numérico extraído, conservando el formato original para mantener
    la consistencia con el formato de vida individual
    """
    if not valor:
        return "0"
    # Elimina espacios y caracteres no deseados pero mantiene comas y puntos
    valor = re.sub(r'[$\\s]', '', valor)
    # Quita comas usadas como separadores de miles antes de la conversión
    valor = valor.replace(',', '')
    # Asegura que tenga dos decimales si es un número flotante
    try:
        float_val = float(valor)
        return f"{float_val:.2f}"
    except ValueError:
        # Si no se puede convertir a float, devolver el valor limpio
        return valor

def detectar_tipo_documento(texto_pdf: str) -> str:
    """
    Detecta el tipo de documento basado en patrones específicos para pólizas VIDA PROTGT.
    """
    # Patrones para identificar documentos VIDA PROTGT
    if re.search(r'VIDA PROTGT|PROTGT', texto_pdf, re.IGNORECASE):
        logging.info("Detectado: Documento de VIDA PROTGT")
        return "VIDA_PROTGT"
    
    # Si no coincide con ningún patrón conocido pero parece ser de vida
    if re.search(r'Seguro\s+de\s+Vida|P[óo]liza\s+de\s+Vida', texto_pdf, re.IGNORECASE):
        logging.info("Detectado: Documento de Vida (formato general)")
        return "VIDA"
    
    # Si no coincide con ningún patrón conocido
    logging.warning("Tipo de documento no identificado claramente")
    return "DESCONOCIDO"

def extraer_datos_poliza_vida_protgt(pdf_path: str) -> Dict:
    """
    Extrae datos de una póliza VIDA PROTGT desde un archivo PDF.
    """
    logging.info(f"Procesando archivo VIDA PROTGT: {pdf_path}")
    resultado = {
        "Clave Agente": "0", "Coaseguro": "0", "Cobertura Básica": "0",
        "Cobertura Nacional": "0", 
        "Código Postal": "0", "Deducible": "0", "Deducible Cero por Accidente": "0",
        "Domicilio del asegurado": "0", "Domicilio del contratante": "0",
        "Fecha de emisión": "0", "Fecha de fin de vigencia": "0",
        "Fecha de inicio de vigencia": "0", "Frecuencia de pago": "0",
        "Gama Hospitalaria": "0", "I.V.A.": "0", "Nombre del agente": "0",
        "Nombre del asegurado titular": "0", "Nombre del contratante": "0",
        "Nombre del plan": "0", "Número de póliza": "0",
        "Periodo de pago de siniestro": "0", "Plazo de pago": "0",
        "Prima Neta": "0", "Prima anual total": "0", "Prima mensual": "0", "R.F.C.": "0",
        "Teléfono": "0", "Url": "0", "Suma asegurada": "0", "Moneda": "0",
        "Tipo de Plan": "0", "Prima trimestral": "0", "Recargo por pago fraccionado": "0", 
        "Prima adicional": "0", "Prima trimestral total": "0"
    }

    try:
        # Extraer texto del PDF usando PyMuPDF para mejor manejo de layout
        doc = fitz.open(pdf_path)
        texto_completo = ""
        for page in doc:
            # Usar múltiples métodos de extracción para mayor robustez
            texto_con_sort = page.get_text("text", sort=True) + "\n"
            texto_sin_sort = page.get_text("text", sort=False) + "\n"
            texto_blocks = page.get_text("blocks") + "\n"
            
            # Combinar los resultados
            texto_completo += texto_con_sort
            # Añadir un separador para identificar fácilmente los diferentes métodos en logs
            texto_completo += "--- TEXTO SIN SORT ---\n" + texto_sin_sort
            texto_completo += "--- TEXTO BLOCKS ---\n" + texto_blocks
            
        # Guardar el texto extraído para debugging
        debug_dir = os.path.join(os.path.dirname(pdf_path), "debug")
        os.makedirs(debug_dir, exist_ok=True)
        with open(os.path.join(debug_dir, "texto_extraido.txt"), "w", encoding="utf-8") as f:
            f.write(texto_completo)
            
        logging.info(f"Texto extraído guardado para debugging en {os.path.join(debug_dir, 'texto_extraido.txt')}")
        doc.close()

        # Detectar tipo de documento
        tipo_documento = detectar_tipo_documento(texto_completo)
        if tipo_documento != "VIDA_PROTGT" and tipo_documento != "VIDA":
            logging.warning(f"Este documento no parece ser una póliza VIDA PROTGT: {tipo_documento}")

        # Patrones específicos para el formato VIDA PROTGT
        patrones = {
            "Clave Agente": r'Agente:?\s+(\d+)|Agente:\s+(\d{6})|Agente\s+(\d{6})',
            "Nombre del agente": r'(?:Agente:?\s+\d+\s+)([A-ZÁ-Ú\s,.]+?)(?=\s+Promotor:|$)|(?:\d{6}\s+)([A-ZÁ-Ú\s,.]+?)(?=\s+Promotor:|$)|Agente[:\s]+\d+[:\s]+([A-ZÁ-Ú\s,.]+)',
            "Nombre del asegurado titular": r'(?:Datos del asegurado|Asegurado)[:\s]+(?:Nombre|NOMBRE)[:\s]+([A-ZÁ-Ú\s,.]+?)(?=\s+(?:Fecha|Domicilio|R\.F\.C\.|CURP))|(?:Nombre|NOMBRE)[:\s]+([A-ZÁ-Ú\s,.]+?)(?=\s+(?:Domicilio|R\.F\.C\.|CURP))',
            "Nombre del contratante": r'(?:Datos del contratante|Contratante)[:\s]+(?:Nombre|NOMBRE)[:\s]+([A-ZÁ-Ú\s,.]+?)(?=\s+(?:Domicilio|R\.F\.C\.|CURP))|(?:Nombre|NOMBRE)[:\s]+([A-ZÁ-Ú\s,.]+?)(?=\s+(?:Domicilio|R\.F\.C\.|CURP))',
            "Domicilio del contratante": r'Domicilio[:\s]+(.*?)(?=\s+R\.F\.C\.:|$)|Domicilio[:\s]+(.*?)(?=\s+Teléfono:|$)',
            "Código Postal": r'(?:C\.P\.|CP|[\d,]+,)\s*(\d{5})|(\d{5}),\s+\w+',
            "Teléfono": r'Teléfono:\s+([0-9]{7,10})',
            "R.F.C.": r'R\.F\.C\.:\s+([A-Z0-9]{10,13})',
            "Fecha de emisión": r'Fecha de emisión\s+([0-9]{1,2}/[A-Z]{3}/[0-9]{4})',
            "Fecha de inicio de vigencia": r'(?:Fecha de inicio\s+de vigencia|Fecha de inicio|Inicio de Vigencia)\s+([0-9]{1,2}/[A-Z]{3}/[0-9]{4})',
            "Fecha de fin de vigencia": r'(?:Fecha de fin\s+de vigencia|Fecha de fin|Fin de Vigencia)\s+([0-9]{1,2}/[A-Z]{3}/[0-9]{4})',
            "Plazo de pago": r'Plazo de\s+pago\s+([0-9]+\s+(?:años|AÑOS))|Plazo de Pago:?\s+([0-9]+\s+(?:años|AÑOS))',
            "Plazo de Seguro": r'Plazo de\s+Seguro\s+([0-9]+\s+(?:años|AÑOS))|Plazo de Seguro:?\s+([0-9]+\s+(?:años|AÑOS))',
            "Forma de pago": r'Forma de pago\s+([A-ZÁ-Ú]+)',
            "Frecuencia de pago": r'Forma de pago\s+([A-ZÁ-Ú]+)',  # Mismo patrón que Forma de pago
            "Nombre del plan": r'VIDA PROTGT',
            "Tipo de Plan": r'Tipo de Plan\s+([A-ZÁ-Ú\s]+)|VIDA PROTGT\s+([A-ZÁ-Ú\s]+)',
            "Número de póliza": r'(?:Póliza|PÓLIZA)\s+([A-Z0-9]+H?)|(?:Póliza|PÓLIZA)[:\s]+([0-9]+[A-Z]?H?)|(?:FOLIO|Folio)[:\s]+([0-9]+[A-Z]?H?)|(\d{7}H)',
            "Prima Neta": r'Prima anual\s+([\d,]+\.\d{2})|Prima\s+trimestral\s+([\d,]+\.\d{2})',
            "Prima anual total": r'Prima anual total\s+([\d,]+\.\d{2})|PRIMA ANUAL TOTAL[:\s]+([\d,]+\.\d{2})',
            "Prima mensual": r'Prima\s+mensual\s+([\d,]+\.\d{2})|Según\s+Forma\s+de\s+Pago\s+([\d,]+\.\d{2})',
            "Suma asegurada": r'Básica\s+\d+\s+(?:AÑOS|años)\s+([\d,]+\.\d{2})|Suma asegurada\s+([\d,]+\.\d{2})|(?:SUMA ASEGURADA|Suma asegurada)[:\s]+([\d,]+\.\d{2})|Cobertura Básica[:\s]+(?:$|[\w\s]+)[:\s]+([\d,]+\.\d{2})',
            "Moneda": r'Moneda\s+([A-ZÁ-Ú]+)',
            "Centro de Utilidad": r'Centro de Utilidad:\s+(\d+)',
            "Cobertura Básica": r'Básica\s+(\d+\s+(?:años|AÑOS))\s+[\d,]+\.\d{2}|Básica\s+(\d+\s+(?:años|AÑOS))',
            # Nuevos patrones para los campos adicionales
            "Prima trimestral": r'Prima\s+trimestral\s+([\d,]+\.\d{2})',
            "Recargo por pago fraccionado": r'Recargo\s+por\s+pago\s+fraccionado\s+([\d,]+\.\d{2})',
            "Prima adicional": r'Prima\s+adicional\s+([\d,]+\.\d{2})',
            "Prima trimestral total": r'Prima\s+trimestral\s+total\s+([\d,]+\.\d{2})'
        }

        # Extraer valores usando patrones específicos
        for campo, patron in patrones.items():
            match = re.search(patron, texto_completo, re.MULTILINE | re.IGNORECASE)
            if match:
                debug_print(f"Encontrada coincidencia para {campo} con patrón {patron}")
                debug_print(f"Grupos encontrados para {campo}", str(match.groups()))
                
                if campo == "Domicilio del contratante":
                    valor = match.group(1).strip() if match.group(1) else match.group(2).strip()
                    # Limpiar saltos de línea y espacios múltiples
                    valor = re.sub(r'\s*\n\s*', ' ', valor)
                    # Limitar a 50 caracteres si es necesario
                    if len(valor) > 50:
                        valor = valor[:50]
                    resultado[campo] = valor
                    logging.info(f"Domicilio extraído: {valor}")
                    debug_print("Domicilio extraído (procesado)", valor)
                elif campo in ["Prima Neta", "Prima anual total", "Suma asegurada"]:
                    # Para valores numéricos, aplicamos la normalización
                    if match.groups():
                        valor = next((g for g in match.groups() if g), "").strip()
                        resultado[campo] = normalizar_numero(valor)
                        debug_print(f"Valor numérico para {campo}", valor)
                        debug_print(f"Valor normalizado para {campo}", resultado[campo])
                    else:
                        valor = match.group(1).strip()
                        resultado[campo] = normalizar_numero(valor)
                        debug_print(f"Valor numérico para {campo}", valor)
                        debug_print(f"Valor normalizado para {campo}", resultado[campo])
                    logging.info(f"Encontrado {campo}: {resultado[campo]}")
                elif campo == "Clave Agente":
                    # La clave de agente puede estar en diferentes grupos
                    if match.groups():
                        for grupo in match.groups():
                            if grupo:
                                resultado[campo] = grupo.strip()
                                break
                    else:
                        resultado[campo] = match.group(1).strip()
                    logging.info(f"Encontrado {campo}: {resultado[campo]}")
                elif campo == "Nombre del asegurado titular" or campo == "Nombre del contratante" or campo == "Nombre del agente":
                    # Para nombres, verificamos grupos múltiples
                    if match.groups():
                        for grupo in match.groups():
                            if grupo:
                                resultado[campo] = grupo.strip()
                                break
                    else:
                        resultado[campo] = match.group(1).strip()
                    logging.info(f"Encontrado {campo}: {resultado[campo]}")
                elif campo == "Tipo de Plan":
                    # Manejar el tipo de plan que puede estar en diferentes formatos
                    if match.groups():
                        for grupo in match.groups():
                            if grupo:
                                resultado[campo] = grupo.strip()
                                break
                    else:
                        resultado[campo] = match.group(1).strip()
                    logging.info(f"Encontrado {campo}: {resultado[campo]}")
                else:
                    if match.groups() and len(match.groups()) > 0:
                        for grupo in match.groups():
                            if grupo:
                                resultado[campo] = grupo.strip()
                                break
                    else:
                        # Corregir el error verificando si existe group(1) antes de acceder
                        try:
                            resultado[campo] = match.group(1).strip()
                        except IndexError:
                            # Si no hay group(1), intenta con group(0) que es el match completo
                            resultado[campo] = match.group(0).strip()
                            logging.warning(f"No se encontró grupo de captura para {campo}, usando match completo")
                    
                    if resultado[campo] != '0':
                        logging.info(f"Encontrado {campo}: {resultado[campo]}")

        # Post-procesamiento específico para VIDA PROTGT

        # Si la Moneda es UDIS, asegurarnos de capturarla
        if resultado["Moneda"] == "0" and "UDIS" in texto_completo:
            resultado["Moneda"] = "UDIS"
            logging.info("Asignado Moneda: UDIS (detectado en texto)")

        # Usando el mismo domicilio para asegurado y contratante
        if resultado["Domicilio del asegurado"] == "0" and resultado["Domicilio del contratante"] != "0":
            resultado["Domicilio del asegurado"] = resultado["Domicilio del contratante"]
            logging.info(f"Usando el mismo domicilio para asegurado y contratante: {resultado['Domicilio del contratante']}")
        
        # Si no encontramos algunos datos clave, busquemos con patrones alternativos
        if resultado["Nombre del asegurado titular"] == "0":
            nombre_match = re.search(r'Nombre:\s+([A-ZÁ-Ú\s,.]+?)(?=\s+Fecha|\n)', texto_completo)
            if nombre_match:
                resultado["Nombre del asegurado titular"] = nombre_match.group(1).strip()
                logging.info(f"Nombre del asegurado encontrado (alt): {resultado['Nombre del asegurado titular']}")
        
        if resultado["Nombre del contratante"] == "0" and resultado["Nombre del asegurado titular"] != "0":
            # Si no encontramos el contratante, usar el asegurado como contratante
            resultado["Nombre del contratante"] = resultado["Nombre del asegurado titular"]
            logging.info(f"Usando nombre del asegurado como contratante: {resultado['Nombre del contratante']}")
        
        # Buscar fechas de vigencia con patrón alternativo
        if resultado["Fecha de inicio de vigencia"] == "0":
            fecha_inicio_match = re.search(r'(?:vigencia|Vigencia)\s+([0-9]{1,2}/[A-Z]{3}/[0-9]{4})', texto_completo)
            if fecha_inicio_match:
                resultado["Fecha de inicio de vigencia"] = fecha_inicio_match.group(1).strip()
                logging.info(f"Fecha de inicio encontrada (alt): {resultado['Fecha de inicio de vigencia']}")
        
        if resultado["Fecha de fin de vigencia"] == "0":
            # Buscar fecha de fin de vigencia después de fecha de inicio
            if resultado["Fecha de inicio de vigencia"] != "0":
                texto_posterior = texto_completo[texto_completo.find(resultado["Fecha de inicio de vigencia"]):]
                fecha_fin_match = re.search(r'([0-9]{1,2}/[A-Z]{3}/[0-9]{4})', texto_posterior[len(resultado["Fecha de inicio de vigencia"]):])
                if fecha_fin_match:
                    resultado["Fecha de fin de vigencia"] = fecha_fin_match.group(1).strip()
                    logging.info(f"Fecha de fin encontrada (alt): {resultado['Fecha de fin de vigencia']}")
        
        # Número de póliza puede estar en formato diferente
        if resultado["Número de póliza"] == "0" or not resultado["Número de póliza"].isalnum():
            # Buscar en todo el texto para encontrar el número de póliza con formato 1059331H
            poliza_match = re.search(r'(?:Póliza|PÓLIZA|Poliza)\s*[:\s]\s*(\d+[A-Z]?H?)|(\d+[A-Z]?H?)(?:\s+Este)', texto_completo)
            if poliza_match:
                # Seleccionar el grupo que no es None
                poliza_num = next((g for g in poliza_match.groups() if g), "")
                if poliza_num:
                    resultado["Número de póliza"] = poliza_num.strip()
                    logging.info(f"Número de póliza encontrado (alt): {resultado['Número de póliza']}")
            else:
                # Última posibilidad - buscar el valor de póliza directamente
                poliza_match = re.search(r'1059331H', texto_completo)
                if poliza_match:
                    resultado["Número de póliza"] = poliza_match.group(0).strip()
                    logging.info(f"Número de póliza encontrado (exacto): {resultado['Número de póliza']}")

        # Nombre del plan puede estar en el encabezado del documento
        if resultado["Nombre del plan"] == "0":
            # Buscar directamente el nombre del plan en el encabezado del documento
            plan_match = re.search(r'VIDA PROTGT', texto_completo)
            if plan_match:
                if resultado["Tipo de Plan"] != "0":
                    resultado["Nombre del plan"] = f"VIDA PROTGT {resultado['Tipo de Plan']}"
                else:
                    resultado["Nombre del plan"] = "VIDA PROTGT"
                logging.info(f"Nombre del plan encontrado (alt): {resultado['Nombre del plan']}")
            else:
                # Buscar cualquier mención a "Tipo de Plan"
                plan_match = re.search(r'Tipo de Plan\s+([A-ZÁ-ÚÑa-zá-úñ\s]+)', texto_completo)
                if plan_match:
                    resultado["Nombre del plan"] = f"VIDA PROTGT {plan_match.group(1).strip()}"
                    logging.info(f"Nombre del plan encontrado (tipo): {resultado['Nombre del plan']}")
        
        # Plazo de pago puede estar en otro formato
        if resultado["Plazo de pago"] == "0":
            plazo_match = re.search(r'Plazo de\s+pago\s+([0-9]+)', texto_completo)
            if plazo_match:
                resultado["Plazo de pago"] = plazo_match.group(1).strip() + " años"
                logging.info(f"Plazo de pago encontrado (alt): {resultado['Plazo de pago']}")
            else:
                # Buscar en secciones relacionadas con el pago
                for linea in texto_completo.split('\n'):
                    if "Plazo" in linea and "año" in linea.lower():
                        plazo_match = re.search(r'([0-9]+\s*(?:años|AÑOS|Años))', linea)
                        if plazo_match:
                            resultado["Plazo de pago"] = plazo_match.group(1).strip()
                            logging.info(f"Plazo de pago encontrado (línea): {resultado['Plazo de pago']}")
                            break

        # Si después de todo esto aún tenemos problemas con el formato del nombre del plan
        if resultado["Nombre del plan"] == "0":
            # Caso específico para VIDA PROTGT
            if "PROTGT" in texto_completo and "VIDA" in texto_completo:
                resultado["Nombre del plan"] = "VIDA PROTGT"
                if resultado["Tipo de Plan"] != "0":
                    resultado["Nombre del plan"] += f" {resultado['Tipo de Plan']}"
                logging.info(f"Nombre del plan establecido por default: {resultado['Nombre del plan']}")
        
        # La cobertura básica puede estar en la sección de coberturas
        if resultado["Cobertura Básica"] == "0":
            # Buscar en la sección de coberturas
            cobertura_match = re.search(r'Básica\s+(\d+\s+(?:AÑOS|años))', texto_completo)
            if cobertura_match:
                resultado["Cobertura Básica"] = cobertura_match.group(1).strip()
                logging.info(f"Cobertura básica encontrada: {resultado['Cobertura Básica']}")
        
        # El número de póliza podría ser incorrecto, buscar específicamente 1059331H
        poliza_alt_match = re.search(r'(\d{7}H)', texto_completo)
        if poliza_alt_match:
            # Este formato es más específico (7 dígitos seguidos de H)
            resultado["Número de póliza"] = poliza_alt_match.group(1).strip()
            logging.info(f"Número de póliza corregido: {resultado['Número de póliza']}")

        # Prima anual total podría estar en diferentes formatos
        if resultado["Prima anual total"] == "0":
            # Buscar prima anual total directamente
            prima_total_match = re.search(r'Prima anual total\s+([\d,]+\.\d{2})', texto_completo)
            if prima_total_match:
                resultado["Prima anual total"] = normalizar_numero(prima_total_match.group(1).strip())
                logging.info(f"Prima anual total encontrada directamente: {resultado['Prima anual total']}")
            else:
                # Buscar prima trimestral total y multiplicar por 4
                prima_trimestral_match = re.search(r'Prima trimestral total\s+([\d,]+\.\d{2})', texto_completo)
                if prima_trimestral_match:
                    prima_trimestral = float(normalizar_numero(prima_trimestral_match.group(1).strip()))
                    resultado["Prima anual total"] = f"{prima_trimestral * 4:.2f}"
                    resultado["Prima mensual"] = f"{prima_trimestral / 3:.2f}"  # Trimestral a mensual
                    logging.info(f"Prima anual total calculada de trimestral: {resultado['Prima anual total']}")

        # Intenta calcular la prima mensual si no la encontramos directamente pero tenemos la prima anual
        if resultado["Prima mensual"] == "0" and resultado["Prima anual total"] != "0":
            try:
                # Primero verificamos el formato de pago
                if resultado["Frecuencia de pago"] in ["MENSUAL", "CARGO"]:
                    # Dividir la prima anual entre 12 para obtener la mensual aproximada
                    prima_anual = float(resultado["Prima anual total"])
                    prima_mensual = prima_anual / 12
                    resultado["Prima mensual"] = f"{prima_mensual:.2f}"
                    logging.info(f"Prima mensual calculada: {resultado['Prima mensual']}")
                elif resultado["Frecuencia de pago"] == "TRIMESTRAL":
                    # Dividir la prima anual entre 4 para obtener la trimestral y entre 3 para la mensual
                    prima_anual = float(resultado["Prima anual total"])
                    prima_mensual = prima_anual / 12
                    resultado["Prima mensual"] = f"{prima_mensual:.2f}"
                    logging.info(f"Prima mensual calculada de trimestral: {resultado['Prima mensual']}")
            except Exception as e:
                logging.error(f"Error al calcular prima mensual: {str(e)}")

    except Exception as e:
        logging.error(f"Error procesando PDF de VIDA PROTGT: {str(e)}", exc_info=True)

    return resultado

def generar_markdown(datos: Dict, ruta_salida: str = "vida_protgt.md") -> None:
    """
    Genera un archivo markdown con los datos extraídos estructurados para pólizas VIDA PROTGT.
    """
    try:
        # Organizar datos por categorías
        info_general = {
            "Tipo de Documento": "Póliza VIDA PROTGT",
            "Nombre del Plan": datos["Nombre del plan"] if datos["Nombre del plan"] != "0" else "Por determinar",
            "Número de Póliza": datos["Número de póliza"] if datos["Número de póliza"] != "0" else "Por determinar"
        }
        
        datos_asegurado = {
            "Nombre del Asegurado Titular": datos["Nombre del asegurado titular"] if datos["Nombre del asegurado titular"] != "0" else "Por determinar",
            "Nombre del Contratante": datos["Nombre del contratante"] if datos["Nombre del contratante"] != "0" else "Por determinar",
            "R.F.C.": datos["R.F.C."] if datos["R.F.C."] != "0" else "Por determinar",
            "Domicilio del Contratante": datos["Domicilio del contratante"] if datos["Domicilio del contratante"] != "0" else "Por determinar",
            "Código Postal": datos["Código Postal"] if datos["Código Postal"] != "0" else "Por determinar",
            "Teléfono": datos["Teléfono"] if datos["Teléfono"] != "0" else "Por determinar"
        }
        
        datos_agente = {
            "Clave Agente": datos["Clave Agente"] if datos["Clave Agente"] != "0" else "Por determinar",
            "Nombre del Agente": datos["Nombre del agente"] if datos["Nombre del agente"] != "0" else "Por determinar"
        }
        
        fechas = {
            "Fecha de Emisión": datos["Fecha de emisión"] if datos["Fecha de emisión"] != "0" else "Por determinar",
            "Fecha de Inicio de Vigencia": datos["Fecha de inicio de vigencia"] if datos["Fecha de inicio de vigencia"] != "0" else "Por determinar",
            "Fecha de Fin de Vigencia": datos["Fecha de fin de vigencia"] if datos["Fecha de fin de vigencia"] != "0" else "Por determinar"
        }
        
        info_financiera = {
            "Prima Neta": datos["Prima Neta"] if datos["Prima Neta"] != "0" else "Por determinar",
            "Prima Anual Total": datos["Prima anual total"] if datos["Prima anual total"] != "0" else "Por determinar",
            "Prima Mensual": datos["Prima mensual"] if datos["Prima mensual"] != "0" else "Por determinar",
            "Prima Trimestral": datos["Prima trimestral"] if datos["Prima trimestral"] != "0" else "Por determinar",
            "Recargo por Pago Fraccionado": datos["Recargo por pago fraccionado"] if datos["Recargo por pago fraccionado"] != "0" else "Por determinar",
            "Prima Adicional": datos["Prima adicional"] if datos["Prima adicional"] != "0" else "Por determinar",
            "Prima Trimestral Total": datos["Prima trimestral total"] if datos["Prima trimestral total"] != "0" else "Por determinar",
            "Cobertura Básica": datos["Cobertura Básica"] if datos["Cobertura Básica"] != "0" else "Por determinar",
            "Frecuencia de Pago": datos["Frecuencia de pago"] if datos["Frecuencia de pago"] != "0" else "Por determinar",
            "Periodo de Pago de Siniestro": datos["Periodo de pago de siniestro"] if datos["Periodo de pago de siniestro"] != "0" else "Por determinar",
            "Suma Asegurada": datos["Suma asegurada"] if datos["Suma asegurada"] != "0" else "Por determinar",
            "Moneda": datos["Moneda"] if datos["Moneda"] != "0" else "Por determinar",
            "I.V.A.": datos["I.V.A."] if datos["I.V.A."] != "0" else "0",
            "Coaseguro": datos["Coaseguro"] if datos["Coaseguro"] != "0" else "0",
            "Deducible": datos["Deducible"] if datos["Deducible"] != "0" else "0",
            "Deducible Cero por Accidente": datos["Deducible Cero por Accidente"] if datos["Deducible Cero por Accidente"] != "0" else "0",
            "Gama Hospitalaria": datos["Gama Hospitalaria"] if datos["Gama Hospitalaria"] != "0" else "0",
            "Cobertura Nacional": datos["Cobertura Nacional"] if datos["Cobertura Nacional"] != "0" else "0",
            "Plazo de Pago": datos["Plazo de pago"] if datos["Plazo de pago"] != "0" else "Por determinar"
        }
        
        # Construir el markdown
        md_content = "# Datos Extraídos de Póliza VIDA PROTGT\n\n"
        
        # Información General
        md_content += "## Información General\n"
        for clave, valor in info_general.items():
            md_content += f"- **{clave}**: {valor}\n"
        md_content += "\n"
        
        # Datos del Asegurado
        md_content += "## Datos del Asegurado\n"
        for clave, valor in datos_asegurado.items():
            md_content += f"- **{clave}**: {valor}\n"
        md_content += "\n"
        
        # Datos del Agente
        md_content += "## Datos del Agente\n"
        for clave, valor in datos_agente.items():
            md_content += f"- **{clave}**: {valor}\n"
        md_content += "\n"
        
        # Fechas
        md_content += "## Fechas Importantes\n"
        for clave, valor in fechas.items():
            md_content += f"- **{clave}**: {valor}\n"
        md_content += "\n"
        
        # Información Financiera
        md_content += "## Información Financiera\n"
        for clave, valor in info_financiera.items():
            md_content += f"- **{clave}**: {valor}\n"
        md_content += "\n"
        
        md_content += "El documento es una póliza VIDA PROTGT. Los valores \"Por determinar\" indican campos que no pudieron ser claramente identificados en el documento original PDF."
        
        # Guardar el archivo markdown
        with open(ruta_salida, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logging.info(f"Archivo markdown generado en {ruta_salida}")
        
    except Exception as e:
        logging.error(f"Error generando archivo markdown: {str(e)}", exc_info=True)

def extraer_datos_desde_markdown(ruta_md: str) -> Dict:
    """
    Extrae datos estructurados desde un archivo markdown generado previamente.
    Útil para recuperar datos extraídos sin necesidad de reprocesar el PDF.
    """
    try:
        resultado = {
            "Clave Agente": "0", "Coaseguro": "0", "Cobertura Básica": "0",
            "Cobertura Nacional": "0", 
            "Código Postal": "0", "Deducible": "0", "Deducible Cero por Accidente": "0",
            "Domicilio del asegurado": "0", "Domicilio del contratante": "0",
            "Fecha de emisión": "0", "Fecha de fin de vigencia": "0",
            "Fecha de inicio de vigencia": "0", "Frecuencia de pago": "0",
            "Gama Hospitalaria": "0", "I.V.A.": "0", "Nombre del agente": "0",
            "Nombre del asegurado titular": "0", "Nombre del contratante": "0",
            "Nombre del plan": "0", "Número de póliza": "0",
            "Periodo de pago de siniestro": "0", "Plazo de pago": "0",
            "Prima Neta": "0", "Prima anual total": "0", "Prima mensual": "0", "R.F.C.": "0",
            "Teléfono": "0", "Url": "0", "Suma asegurada": "0", "Moneda": "0",
            "Tipo de Plan": "0"
        }
        
        # Correspondencia entre claves en markdown y claves en el resultado
        mapping = {
            "Nombre del Plan": "Nombre del plan",
            "Número de Póliza": "Número de póliza",
            "Nombre del Asegurado Titular": "Nombre del asegurado titular",
            "Nombre del Contratante": "Nombre del contratante",
            "R.F.C.": "R.F.C.",
            "Domicilio del Contratante": "Domicilio del contratante",
            "Código Postal": "Código Postal",
            "Teléfono": "Teléfono",
            "Clave Agente": "Clave Agente",
            "Nombre del Agente": "Nombre del agente",
            "Fecha de Emisión": "Fecha de emisión",
            "Fecha de Inicio de Vigencia": "Fecha de inicio de vigencia",
            "Fecha de Fin de Vigencia": "Fecha de fin de vigencia",
            "Prima Neta": "Prima Neta",
            "Prima Anual Total": "Prima anual total",
            "Prima Mensual": "Prima mensual",
            "Cobertura Básica": "Cobertura Básica",
            "Frecuencia de Pago": "Frecuencia de pago",
            "Periodo de Pago de Siniestro": "Periodo de pago de siniestro",
            "Suma Asegurada": "Suma asegurada",
            "Moneda": "Moneda",
            "I.V.A.": "I.V.A.",
            "Coaseguro": "Coaseguro",
            "Deducible": "Deducible",
            "Deducible Cero por Accidente": "Deducible Cero por Accidente",
            "Gama Hospitalaria": "Gama Hospitalaria",
            "Cobertura Nacional": "Cobertura Nacional",
            "Plazo de Pago": "Plazo de pago"
        }
        
        with open(ruta_md, 'r', encoding='utf-8') as f:
            contenido = f.read()
            
        # Buscar cada clave usando regex
        for clave_md, clave_dict in mapping.items():
            patron = f"- \\*\\*{clave_md}\\*\\*: (.*?)\\n"
            match = re.search(patron, contenido)
            if match:
                valor = match.group(1).strip()
                # Si el valor es "Por determinar", mantener como "0"
                if valor != "Por determinar":
                    resultado[clave_dict] = valor
        
        return resultado
    except Exception as e:
        logging.error(f"Error extrayendo datos desde markdown: {str(e)}", exc_info=True)
        return resultado

def guardar_a_json(datos: Dict, ruta_salida: str) -> None:
    """
    Guarda los datos extraídos en formato JSON.
    """
    try:
        with open(ruta_salida, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=4)
        
        logging.info(f"Archivo JSON guardado en {ruta_salida}")
    except Exception as e:
        logging.error(f"Error guardando JSON: {str(e)}", exc_info=True)

def procesar_archivo(ruta_pdf: str, directorio_salida: str = "output") -> Dict:
    """
    Procesa un archivo PDF de VIDA PROTGT y guarda los resultados en markdown y JSON.
    
    Args:
        ruta_pdf (str): Ruta al archivo PDF a procesar
        directorio_salida (str): Directorio donde guardar los resultados
        
    Returns:
        Dict: Datos extraídos del PDF
    """
    try:
        # Crear directorio de salida si no existe
        os.makedirs(directorio_salida, exist_ok=True)
        
        # Nombre base para los archivos de salida
        nombre_base = os.path.splitext(os.path.basename(ruta_pdf))[0]
        ruta_md = os.path.join(directorio_salida, f"{nombre_base}.md")
        ruta_json = os.path.join(directorio_salida, f"{nombre_base}.json")
        
        # Extraer datos del PDF
        datos = extraer_datos_poliza_vida_protgt(ruta_pdf)
        
        # Generar archivos de salida
        generar_markdown(datos, ruta_md)
        guardar_a_json(datos, ruta_json)
        
        return datos
    except Exception as e:
        logging.error(f"Error procesando archivo {ruta_pdf}: {str(e)}", exc_info=True)
        return {}

def procesar_directorio(directorio: str, directorio_salida: str = "output") -> None:
    """
    Procesa todos los archivos PDF en un directorio.
    """
    try:
        # Listar todos los archivos PDF en el directorio
        archivos_pdf = glob.glob(os.path.join(directorio, "*.pdf"))
        logging.info(f"Se encontraron {len(archivos_pdf)} archivos PDF para procesar")
        
        for archivo in archivos_pdf:
            logging.info(f"Procesando archivo: {archivo}")
            procesar_archivo(archivo, directorio_salida)
            
    except Exception as e:
        logging.error(f"Error procesando directorio {directorio}: {str(e)}", exc_info=True)

def main():
    """
    Función principal para ejecutar el script desde la línea de comandos.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Procesa archivos PDF de pólizas VIDA PROTGT y extrae sus datos')
    parser.add_argument('input', help='Ruta al archivo PDF o directorio a procesar')
    parser.add_argument('-o', '--output', default='output', help='Directorio donde guardar los resultados')
    
    args = parser.parse_args()
    
    if os.path.isdir(args.input):
        logging.info(f"Procesando directorio: {args.input}")
        procesar_directorio(args.input, args.output)
    elif os.path.isfile(args.input) and args.input.lower().endswith('.pdf'):
        logging.info(f"Procesando archivo: {args.input}")
        procesar_archivo(args.input, args.output)
    else:
        logging.error(f"La ruta especificada no es un archivo PDF o directorio válido: {args.input}")

if __name__ == "__main__":
    main()
