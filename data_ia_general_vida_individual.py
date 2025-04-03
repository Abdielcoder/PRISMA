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
    Detecta el tipo de documento basado en patrones específicos para pólizas individuales.
    """
    # Patrones mejorados para identificar documentos de vida individual
    if re.search(r'Vida\s+Individual|Seguro\s+Individual|P[óo]liza\s+Individual|Seguro\s+de\s+Vida\s+Individual|Vida\s+Inteligente', texto_pdf, re.IGNORECASE):
        logging.info("Detectado: Documento de Vida Individual")
        return "VIDA_INDIVIDUAL"
    
    # Si no coincide con ningún patrón conocido pero parece ser de vida
    if re.search(r'Ordinario\s+de\s+Vida|Seguro\s+de\s+Vida|P[óo]liza\s+de\s+Vida', texto_pdf, re.IGNORECASE):
        logging.info("Detectado: Documento de Vida (formato general)")
        return "VIDA"
    
    # Si no coincide con ningún patrón conocido
    logging.warning("Tipo de documento no identificado claramente")
    return "DESCONOCIDO"

def extraer_datos_poliza_vida_individual(pdf_path: str) -> Dict:
    """
    Extrae datos de una póliza de vida individual desde un archivo PDF.
    """
    logging.info(f"Procesando archivo de vida individual: {pdf_path}")
    resultado = {
        "Clave Agente": "0", "Coaseguro": "0", "Cobertura Básica": "0",
        "Cobertura Nacional": "0", "Coberturas adicionales con costo": "0",
        "Código Postal": "0", "Deducible": "0", "Deducible Cero por Accidente": "0",
        "Domicilio del asegurado": "0", "Domicilio del contratante": "0",
        "Fecha de emisión": "0", "Fecha de fin de vigencia": "0",
        "Fecha de inicio de vigencia": "0", "Frecuencia de pago": "0",
        "Gama Hospitalaria": "0", "I.V.A.": "0", "Nombre del agente": "0",
        "Nombre del asegurado titular": "0", "Nombre del contratante": "0",
        "Nombre del plan": "0", "Número de póliza": "0",
        "Periodo de pago de siniestro": "0", "Plazo de pago": "0",
        "Prima Neta": "0", "Prima anual total": "0", "R.F.C.": "0",
        "Teléfono": "0", "Url": "0", "Suma asegurada": "0", "Moneda": "0"
    }

    try:
        # Extraer texto del PDF usando PyMuPDF para mejor manejo de layout
        doc = fitz.open(pdf_path)
        texto_completo = ""
        for page in doc:
            texto_completo += page.get_text("text", sort=True) + "\n" # Usar sort=True para orden de lectura
        doc.close()

        # Detectar tipo de documento
        tipo_documento = detectar_tipo_documento(texto_completo)
        if tipo_documento != "VIDA_INDIVIDUAL" and tipo_documento != "VIDA":
            logging.warning(f"Este documento no parece ser una póliza de vida individual: {tipo_documento}")

        # Patrones Refinados - Enfoque más robusto
        patrones = {
            "Clave Agente": r'Agente\s+(\d+)',
            # Captura nombres permitiendo varias palabras y comas
            "Nombre del asegurado titular": r'Datos del Asegurado\s+Nombre\s+([A-ZÁ-Ú,\s]+?)\s+(?:Fecha de Nacimiento|Sexo)',
            "Nombre del contratante": r'Contratante\s+Nombre\s+([A-ZÁ-Ú,\s]+?)(?=\s+Domicilio)',
            # Domicilio: Captura todo desde "Domicilio" hasta la línea antes de R.F.C., C.P., o Tel.
            "Domicilio del contratante": r'Domicilio\s+((?:.|\n)+?)(?=\n\s*(?:R\.F\.C\.|C\.P\.|Tel\.))',
            "Código Postal": r'C\.P\.\s+(\d{5})',
            "Teléfono": r'Tel\.\s+([0-9]{7,10})',  # Mejora: Limita a 7-10 dígitos
            # RFC: Busca la etiqueta R.F.C. seguida de 10-13 caracteres alfanuméricos
            "R.F.C.": r'R\.F\.C\.\s+([A-Z0-9]{10,13})',
            "Fecha de emisión": r'Emisi[oó]n\s+(\d{1,2}/\w+/\d{4})',
            "Fecha de inicio de vigencia": r'Inicio\s+de\s+Vigencia\s+(\d{1,2}/\w+/\d{4})',
            # Plazo de pago: Busca en la tabla de coberturas, mejorado para capturar "Años" correctamente
            "Plazo de pago": r'VIDA INTELIGENTE CRECIENTE\s+(?:[\d,.]+\s+){2}(\d+\s*A[ñn]os|Vitalicio)',
            "Frecuencia de pago": r'Frecuencia\s+de\s+Pago\s+de\s+Primas\s+([A-Z]+)',
            # Nombre Agente: Corrección de sintaxis en el lookahead
            "Nombre del agente": r'Agente\s+\d+\s+([A-ZÁ-Ú\s]+?)(?=\s+Centro|\n)',
            "Nombre del plan": r'Seguro\s+(VIDA INTELIGENTE(?:\s*\(INDIVIDUAL\))?)',
            "Número de póliza": r'P[óo]liza(?:\s*(?:No\.?|N[úu]mero))?\s*:?\s*([A-Z0-9-]+)',
            "Prima Neta": r'Prima\s+B[áa]sica\s+Anual\s+([\d,]+\.\d{2})',
            "Prima anual total": r'Prima\s+Total\s+Anual\s+([\d,]+\.\d{2})',
            # Suma Asegurada: Busca el primer valor monetario en la línea de VIDA INTELIGENTE CRECIENTE
            "Suma asegurada": r'VIDA INTELIGENTE CRECIENTE\s+([\d,]+\.\d{2})',
            "Moneda": r'Moneda\s+([A-Z]+)'
        }

        # Extraer valores usando patrones mejorados (UN SOLO BUCLE FOR)
        for campo, patron in patrones.items():
            match = re.search(patron, texto_completo, re.MULTILINE | re.IGNORECASE)
            if match:
                valor = next((g for g in match.groups() if g), "").strip()
                if campo == "Domicilio del contratante":
                    valor = re.sub(r'\s*\n\s*', ' ', valor).strip()
                    valor = re.sub(r'(?<=TIJUANA TIJUANA).*$', '', valor).strip() # Limpieza post-captura

                if campo in ["Prima Neta", "Prima anual total", "Suma asegurada"]:
                    resultado[campo] = normalizar_numero(valor)
                elif campo == "R.F.C.":
                    rfc_matches = re.findall(patron, texto_completo, re.MULTILINE | re.IGNORECASE)
                    if rfc_matches:
                        valid_rfcs = [r for r in rfc_matches if len(r) in (12, 13)]
                        if valid_rfcs:
                             resultado[campo] = valid_rfcs[0]
                        elif rfc_matches:
                             resultado[campo] = rfc_matches[0]
                elif valor:
                     resultado[campo] = valor

                if resultado[campo] != '0':
                     logging.info(f"Encontrado {campo}: {resultado[campo]}")

        # Lógica de post-procesamiento o valores por defecto si es necesario
        # (Se puede mantener la lógica para Moneda, Frecuencia de Pago si fallan los regex)

        # Si no se encontró moneda pero hay indicadores en el texto
        if resultado["Moneda"] == "0":
            if "Pesos" in texto_completo or "Nacional" in texto_completo or "MXN" in texto_completo:
                resultado["Moneda"] = "NACIONAL"
                logging.info("Asignado Moneda: NACIONAL (detectado en texto)")
            elif "USD" in texto_completo or "Dólares" in texto_completo or "Dolares" in texto_completo:
                resultado["Moneda"] = "DÓLARES"
                logging.info("Asignado Moneda: DÓLARES (detectado en texto)")

        # Si la Frecuencia de pago es incorrecta, intentar detectarla directamente
        if resultado["Frecuencia de pago"] == "0" or len(resultado["Frecuencia de pago"]) <= 2:
            if "ANUAL" in texto_completo.upper(): # Buscar en mayúsculas
                resultado["Frecuencia de pago"] = "ANUAL"
                logging.info("Asignado Frecuencia de pago: ANUAL (detectado en texto)")
            # ... (otras frecuencias)

        # Lógica para Fecha de Fin de Vigencia (si se usa Plazo de Pago)
        if resultado["Fecha de fin de vigencia"] == "0" and resultado["Plazo de pago"] != "0":
             # Podríamos mantener la lógica de usar el Plazo de Pago o dejarlo como "0"
             # resultado["Fecha de fin de vigencia"] = resultado["Plazo de pago"]
             # logging.info(f"Usando Plazo de Pago como Fecha de Fin de Vigencia: {resultado['Plazo de pago']}")
             pass # Opcionalmente, no asignar nada si no se encontró explícitamente

    except Exception as e:
        logging.error(f"Error procesando PDF de vida individual: {str(e)}", exc_info=True)

    return resultado

def generar_markdown(datos: Dict, ruta_salida: str = "vida_individual.md") -> None:
    """
    Genera un archivo markdown con los datos extraídos estructurados para pólizas de vida individual.
    """
    try:
        # Organizar datos por categorías
        info_general = {
            "Tipo de Documento": "Póliza de Vida Individual",
            "Nombre del Plan": datos["Nombre del plan"].replace("Nombre del plan: ", "") if datos["Nombre del plan"] != "0" else "Por determinar",
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
            "Cobertura Básica": datos["Cobertura Básica"] if datos["Cobertura Básica"] != "0" else "Por determinar",
            "Coberturas Adicionales con Costo": datos["Coberturas adicionales con costo"] if datos["Coberturas adicionales con costo"] != "0" else "Por determinar",
            "Frecuencia de Pago": datos["Frecuencia de pago"] if datos["Frecuencia de pago"] != "0" else "Por determinar",
            "Periodo de Pago de Siniestro": datos["Periodo de pago de siniestro"] if datos["Periodo de pago de siniestro"] != "0" else "Por determinar",
            "Suma Asegurada": datos["Suma asegurada"] if datos["Suma asegurada"] != "0" else "Por determinar",
            "I.V.A.": datos["I.V.A."] if datos["I.V.A."] != "0" else "0",
            "Coaseguro": datos["Coaseguro"] if datos["Coaseguro"] != "0" else "0",
            "Deducible": datos["Deducible"] if datos["Deducible"] != "0" else "0",
            "Deducible Cero por Accidente": datos["Deducible Cero por Accidente"] if datos["Deducible Cero por Accidente"] != "0" else "0",
            "Gama Hospitalaria": datos["Gama Hospitalaria"] if datos["Gama Hospitalaria"] != "0" else "0",
            "Cobertura Nacional": datos["Cobertura Nacional"] if datos["Cobertura Nacional"] != "0" else "0",
            "Plazo de Pago": datos["Plazo de pago"] if datos["Plazo de pago"] != "0" else "Por determinar"
        }
        
        # Construir el markdown
        md_content = "# Datos Extraídos de Póliza de Vida Individual\n\n"
        
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
        
        # Notas
        md_content += "## Notas Adicionales\n"
        md_content += "El documento es una póliza de vida individual. Los valores \"Por determinar\" indican campos que no pudieron ser claramente identificados en el documento original PDF."
        
        # Guardar el archivo markdown
        with open(ruta_salida, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logging.info(f"Archivo markdown generado en {ruta_salida}")
        
    except Exception as e:
        logging.error(f"Error generando archivo markdown: {str(e)}", exc_info=True)

def extraer_datos_desde_markdown(ruta_md: str) -> Dict:
    """
    Extrae datos desde un archivo markdown estructurado para vida individual
    """
    logging.info(f"Extrayendo datos desde archivo markdown: {ruta_md}")
    
    resultado = {
        "Clave Agente": "0", "Coaseguro": "0", "Cobertura Básica": "0",
        "Cobertura Nacional": "0", "Coberturas adicionales con costo": "0",
        "Código Postal": "0", "Deducible": "0", "Deducible Cero por Accidente": "0",
        "Domicilio del asegurado": "0", "Domicilio del contratante": "0",
        "Fecha de emisión": "0", "Fecha de fin de vigencia": "0",
        "Fecha de inicio de vigencia": "0", "Frecuencia de pago": "0",
        "Gama Hospitalaria": "0", "I.V.A.": "0", "Nombre del agente": "0",
        "Nombre del asegurado titular": "0", "Nombre del contratante": "0",
        "Nombre del plan": "0", "Número de póliza": "0",
        "Periodo de pago de siniestro": "0", "Plazo de pago": "0",
        "Prima Neta": "0", "Prima anual total": "0", "R.F.C.": "0",
        "Teléfono": "0", "Url": "0", "Suma asegurada": "0", "Moneda": "0"
    }
    campos_map = {
            "Tipo de Documento": None, # Ignorar
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
            "Cobertura Básica": "Cobertura Básica",
            "Coberturas Adicionales con Costo": "Coberturas adicionales con costo",
            "Frecuencia de Pago": "Frecuencia de pago",
            "Moneda": "Moneda", # Mapear Moneda
            "Periodo de Pago de Siniestro": "Periodo de pago de siniestro",
            "Suma Asegurada": "Suma asegurada",
            "I.V.A.": "I.V.A.",
            "Coaseguro": "Coaseguro",
            "Deducible": "Deducible",
            "Deducible Cero por Accidente": "Deducible Cero por Accidente",
            "Gama Hospitalaria": "Gama Hospitalaria",
            "Cobertura Nacional": "Cobertura Nacional",
            "Plazo de Pago": "Plazo de pago"
        }
        
    try:
        with open(ruta_md, 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        # Extraer los valores con regex
        for md_key, json_key in campos_map.items():
            if json_key: # Solo procesar si la clave JSON no es None
                patron = f"\\*\\*{re.escape(md_key)}\\*\\*: ([^\\n]+)"
                match = re.search(patron, contenido)
                if match:
                    valor = match.group(1).strip()
                    if valor != "Por determinar":
                        resultado[json_key] = valor
                        logging.info(f"Extraído desde markdown: {json_key} = {valor}")
                    else:
                        logging.info(f"Campo {json_key} marcado como 'Por determinar' en markdown.")
                else:
                     logging.warning(f"No se encontró el patrón para '{md_key}' en {ruta_md}")
        
    except FileNotFoundError:
        logging.error(f"Archivo markdown no encontrado: {ruta_md}")
        return resultado # Devuelve el diccionario inicializado si no se encuentra el archivo
    except Exception as e:
        logging.error(f"Error leyendo o procesando archivo markdown {ruta_md}: {e}", exc_info=True)

    # Lógica para domicilio asegurado = contratante
    if resultado["Domicilio del contratante"] != "0":
        logging.info(f"Usando el mismo domicilio para asegurado y contratante: {resultado['Domicilio del contratante']}")
        resultado["Domicilio del asegurado"] = resultado["Domicilio del contratante"]

    return resultado

def guardar_a_json(datos: Dict, ruta_salida: str) -> None:
    """
    Guarda los resultados en formato JSON
    """
    try:
        # Asegurar que ningún valor sea None para evitar errores de serialización
        for clave in datos:
            if datos[clave] is None:
                datos[clave] = "0"
                
        with open(ruta_salida, 'w', encoding='utf-8') as f:
            json.dump({"data": datos}, f, indent=4, ensure_ascii=False)
        logging.info(f"Datos guardados en {ruta_salida}")
    except Exception as e:
        logging.error(f"Error guardando JSON: {str(e)}")

def procesar_archivo(ruta_pdf: str, directorio_salida: str = "output") -> Dict:
    """
    Procesa un único archivo PDF y guarda los resultados
    """
    os.makedirs(directorio_salida, exist_ok=True)
    
    nombre_base = os.path.basename(ruta_pdf).replace('.pdf', '')
    ruta_json = os.path.join(directorio_salida, f"{nombre_base}.json")
    ruta_md = f"{nombre_base}_individual.md"
    
    # Verificar si existe el archivo markdown, si no existe, crear uno
    if not os.path.exists(ruta_md):
        # Extraer datos del PDF
        datos = extraer_datos_poliza_vida_individual(ruta_pdf)
        # Generar archivo markdown con los datos extraídos
        generar_markdown(datos, ruta_md)
        logging.info(f"Archivo markdown creado: {ruta_md}")
    else:
        logging.info(f"Usando archivo markdown existente: {ruta_md}")
    
    # Extraer datos desde el markdown (puede incluir información manual)
    datos_finales = extraer_datos_desde_markdown(ruta_md)
    
    # Guardar los datos extraídos del markdown en JSON
    guardar_a_json(datos_finales, ruta_json)
    
    return datos_finales

def procesar_directorio(directorio: str, directorio_salida: str = "output") -> None:
    """
    Procesa todos los archivos PDF en un directorio
    """
    os.makedirs(directorio_salida, exist_ok=True)
    
    archivos_pdf = glob.glob(os.path.join(directorio, "*.pdf"))
    logging.info(f"Encontrados {len(archivos_pdf)} archivos PDF para procesar")
    
    for ruta_pdf in archivos_pdf:
        procesar_archivo(ruta_pdf, directorio_salida)

def main():
    """
    Función principal para ejecutar el script desde línea de comandos
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Extractor de datos de pólizas de vida individual desde PDFs")
    parser.add_argument("entrada", help="Ruta al archivo PDF o directorio con PDFs")
    parser.add_argument("--salida", default="output", help="Directorio para guardar los resultados")
    args = parser.parse_args()
    
    if os.path.isdir(args.entrada):
        procesar_directorio(args.entrada, args.salida)
    elif os.path.isfile(args.entrada) and args.entrada.lower().endswith('.pdf'):
        procesar_archivo(args.entrada, args.salida)
    else:
        logging.error(f"La ruta de entrada no es válida o no es un archivo PDF: {args.entrada}")
        sys.exit(1)

if __name__ == "__main__":
    main() 