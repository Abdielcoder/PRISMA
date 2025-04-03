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
    la consistencia con el formato de vida.json
    """
    if not valor:
        return "0"
    
    # Elimina espacios y caracteres no deseados pero mantiene comas y puntos
    valor = re.sub(r'[$\s]', '', valor)
    return valor

def detectar_tipo_documento(texto_pdf: str) -> str:
    """
    Detecta el tipo de documento basado en patrones específicos.
    """
    # Patrones para identificar documentos de vida
    if re.search(r'Ordinario de Vida|Seguro de Vida|P[óo]liza de Vida', texto_pdf, re.IGNORECASE):
        logging.info("Detectado: Documento de Vida")
        return "VIDA"
    
    # Si no coincide con ningún patrón conocido
    logging.warning("Tipo de documento no identificado claramente")
    return "DESCONOCIDO"

def extraer_datos_poliza_vida(pdf_path: str) -> Dict:
    """
    Extrae datos de una póliza de vida desde un archivo PDF.
    """
    logging.info(f"Procesando archivo: {pdf_path}")
    resultado = {
        "Clave Agente": "0",
        "Coaseguro": "0",
        "Cobertura Básica": "0",
        "Cobertura Nacional": "0",
        "Coberturas adicionales con costo": "0",
        "Código Postal": "0",
        "Deducible": "0",
        "Deducible Cero por Accidente": "0",
        "Domicilio del asegurado": "0",
        "Domicilio del contratante": "0",
        "Fecha de emisión": "0",
        "Fecha de fin de vigencia": "0",
        "Fecha de inicio de vigencia": "0",
        "Frecuencia de pago": "0",
        "Gama Hospitalaria": "0",
        "I.V.A.": "0",
        "Nombre del agente": "0",
        "Nombre del asegurado titular": "0",
        "Nombre del contratante": "0",
        "Nombre del plan": "0",
        "Número de póliza": "0",
        "Periodo de pago de siniestro": "0",
        "Plazo de pago": "0",
        "Prima Neta": "0",
        "Prima anual total": "0",
        "R.F.C.": "0",
        "Teléfono": "0",
        "Url": "0"
    }
    
    try:
        # Extraer texto del PDF
        reader = PdfReader(pdf_path)
        if len(reader.pages) < 1:
            logging.error(f"El PDF {pdf_path} no tiene páginas")
            return resultado
        
        # Extraer todo el texto del documento para análisis completo
        texto_completo = ""
        for pagina in reader.pages:
            texto_completo += pagina.extract_text() + "\n"
        
        # También usar PyMuPDF para extracción más precisa de tablas y formatos
        doc = fitz.open(pdf_path)
        texto_mupdf = ""
        for pagina in doc:
            texto_mupdf += pagina.get_text() + "\n"
        doc.close()
        
        # Detectar tipo de documento
        tipo_documento = detectar_tipo_documento(texto_completo)
        if tipo_documento != "VIDA":
            logging.warning(f"Este documento no parece ser una póliza de vida: {tipo_documento}")
        
        # Patrones para extracción (ajustados a documentos de vida)
        patrones = {
            "Clave Agente": r'Clave(?:\s+de)?\s+Agente[:\s]+([A-Z0-9]+)|Consultor\s+Financiero\s+([A-Z0-9]+)',
            "Cobertura Básica": r'Cobertura\s+B[áa]sica[:\s]+([\d,.]+)',
            "Código Postal": r'C[óo]digo\s+Postal[:\s]+(\d+)|C\.P\.[:\s]+(\d+)',
            "Fecha de emisión": r'Fecha\s+de\s+emisi[óo]n[:\s]+(\d{1,2}/\w+/\d{4}|\d{1,2}/\d{1,2}/\d{4})',
            "Fecha de fin de vigencia": r'Fecha\s+(?:de\s+fin|fin)\s+de\s+vigencia[:\s]+(\d{1,2}/\w+/\d{4}|\d{1,2}/\d{1,2}/\d{4})',
            "Fecha de inicio de vigencia": r'Fecha\s+(?:de\s+inicio|inicio)\s+de\s+vigencia[:\s]+(\d{1,2}/\w+/\d{4}|\d{1,2}/\d{1,2}/\d{4})',
            "Frecuencia de pago": r'Frecuencia\s+de\s+[Pp]ago(?:\s+de\s+[Pp]rimas)?[:\s]+([\d,.]+|ANUAL|Anual|Mensual|Trimestral|Semestral)',
            "Nombre del agente": r'Nombre\s+del\s+agente[:\s]+([^\n]+)|Consultor\s+Financiero\s+[A-Z0-9]+\s+([A-Z\s]+)',
            "Nombre del asegurado titular": r'Nombre\s+del\s+asegurado\s+titular[:\s]+([^\n]+)',
            "Nombre del contratante": r'Nombre\s+del\s+contratante[:\s]+([^\n]+)',
            "Nombre del plan": r'(?:Nombre\s+del\s+plan|Plan)[:\s]+([^\n]+)',
            "Número de póliza": r'N[úu]mero\s+de\s+p[óo]liza[:\s]+([A-Z0-9]+)',
            "Periodo de pago de siniestro": r'Periodo\s+de\s+pago\s+de\s+siniestro[:\s]+([\d,.]+)',
            "Plazo de pago": r'Plazo\s+(?:de\s+)?[Pp]ago[:\s]+([^\n]+)|Plazo\s+Pago\s+(Vitalicio)',
            "Prima Neta": r'Prima\s+Neta[:\s]+([\d,.]+)',
            "Prima anual total": r'Prima\s+anual\s+total[:\s]+([\d,.]+)',
            "R.F.C.": r'R\.F\.C\.[:\s]+([A-Z0-9]+)',
            "Teléfono": r'Tel\.?[:\s]+([0-9\-\(\)]+)'
        }
        
        # Extraer valores usando patrones
        for campo, patron in patrones.items():
            match = re.search(patron, texto_completo, re.IGNORECASE)
            if match:
                # Para el Código Postal, verificar los grupos de captura
                if campo == "Código Postal" and len(match.groups()) > 1:
                    valor = next((g for g in match.groups() if g), "")
                # Para el Plazo de pago, verificar múltiples grupos de captura
                elif campo == "Plazo de pago" and len(match.groups()) > 1:
                    valor = next((g for g in match.groups() if g), "")
                # Para la Clave Agente, verificar múltiples grupos de captura
                elif campo == "Clave Agente" and len(match.groups()) > 1:
                    valor = next((g for g in match.groups() if g), "")
                # Para el Nombre del agente, verificar múltiples grupos de captura
                elif campo == "Nombre del agente" and len(match.groups()) > 1:
                    valor = next((g for g in match.groups() if g), "")
                else:
                    valor = match.group(1).strip()
                    
                if re.search(r'[\d,.]+', valor) and "fecha" not in campo.lower():
                    resultado[campo] = normalizar_numero(valor)
                else:
                    resultado[campo] = valor
                logging.info(f"Encontrado {campo}: {valor}")
        
        # Verificación específica para "Nombre del plan" que puede tener un formato particular
        if "Ordinario de Vida" in texto_completo:
            resultado["Nombre del plan"] = "Nombre del plan: Ordinario de Vida"
        
        # Si el archivo fue cargado desde una URL, guardar la URL
        if pdf_path.startswith("http"):
            resultado["Url"] = pdf_path
        
        # Buscar específicamente "Plazo Pago" en formato de tabla
        plazo_pago_match = re.search(r'Plazo\s+Pago\s+(\w+)', texto_completo, re.IGNORECASE)
        if plazo_pago_match:
            valor_plazo = plazo_pago_match.group(1).strip()
            logging.info(f"Encontrado Plazo de Pago (formato tabla): {valor_plazo}")
            resultado["Plazo de pago"] = valor_plazo
        
        # Buscar el nombre del agente después de la clave del agente si está en el formato de consultor financiero
        if resultado["Clave Agente"] != "0" and resultado["Nombre del agente"] == "0":
            agente_match = re.search(r'(?:Consultor\s+Financiero|Clave\s+(?:de\s+)?Agente)[:\s]+' + re.escape(resultado["Clave Agente"]) + r'\s+([A-Z\s]+)', texto_completo, re.IGNORECASE)
            if agente_match:
                resultado["Nombre del agente"] = agente_match.group(1).strip()
                logging.info(f"Encontrado Nombre del agente después de clave: {resultado['Nombre del agente']}")
        
    except Exception as e:
        logging.error(f"Error procesando PDF de vida: {str(e)}", exc_info=True)
    
    return resultado

def generar_markdown(datos: Dict, ruta_salida: str = "vida.md") -> None:
    """
    Genera un archivo markdown con los datos extraídos estructurados.
    """
    try:
        # Organizar datos por categorías
        info_general = {
            "Tipo de Documento": "Póliza de Vida",
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
            "I.V.A.": datos["I.V.A."] if datos["I.V.A."] != "0" else "0",
            "Coaseguro": datos["Coaseguro"] if datos["Coaseguro"] != "0" else "0",
            "Deducible": datos["Deducible"] if datos["Deducible"] != "0" else "0",
            "Deducible Cero por Accidente": datos["Deducible Cero por Accidente"] if datos["Deducible Cero por Accidente"] != "0" else "0",
            "Gama Hospitalaria": datos["Gama Hospitalaria"] if datos["Gama Hospitalaria"] != "0" else "0",
            "Cobertura Nacional": datos["Cobertura Nacional"] if datos["Cobertura Nacional"] != "0" else "0",
            "Plazo de Pago": datos["Plazo de pago"] if datos["Plazo de pago"] != "0" else "Por determinar"
        }
        
        # Construir el markdown
        md_content = "# Datos Extraídos de Póliza de Vida\n\n"
        
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
        md_content += "El documento es una póliza ordinaria de vida. Los valores \"Por determinar\" indican campos que no pudieron ser claramente identificados en el documento original PDF."
        
        # Guardar el archivo markdown
        with open(ruta_salida, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logging.info(f"Archivo markdown generado en {ruta_salida}")
        
    except Exception as e:
        logging.error(f"Error generando archivo markdown: {str(e)}", exc_info=True)

def extraer_datos_desde_markdown(ruta_md: str) -> Dict:
    """
    Extrae datos desde un archivo markdown estructurado
    """
    resultado = {
        "Clave Agente": "0",
        "Coaseguro": "0",
        "Cobertura Básica": "0",
        "Cobertura Nacional": "0",
        "Coberturas adicionales con costo": "0",
        "Código Postal": "0",
        "Deducible": "0",
        "Deducible Cero por Accidente": "0",
        "Domicilio del asegurado": "0",
        "Domicilio del contratante": "0",
        "Fecha de emisión": "0",
        "Fecha de fin de vigencia": "0",
        "Fecha de inicio de vigencia": "0",
        "Frecuencia de pago": "0",
        "Gama Hospitalaria": "0",
        "I.V.A.": "0",
        "Nombre del agente": "0",
        "Nombre del asegurado titular": "0",
        "Nombre del contratante": "0",
        "Nombre del plan": "0",
        "Número de póliza": "0",
        "Periodo de pago de siniestro": "0",
        "Plazo de pago": "0",
        "Prima Neta": "0",
        "Prima anual total": "0",
        "R.F.C.": "0",
        "Teléfono": "0",
        "Url": "0"
    }
    
    try:
        # Mapeo de campos del markdown a keys en el resultado
        mappings = {
            "Clave Agente": "Clave Agente",
            "Nombre del Agente": "Nombre del agente",
            "Nombre del Contratante": "Nombre del contratante",
            "Domicilio del Contratante": "Domicilio del contratante",
            "Código Postal": "Código Postal",
            "Teléfono": "Teléfono",
            "R.F.C.": "R.F.C.",
            "Fecha de Emisión": "Fecha de emisión",
            "Fecha de Inicio de Vigencia": "Fecha de inicio de vigencia",
            "Fecha de Fin de Vigencia": "Fecha de fin de vigencia",
            "Prima Neta": "Prima Neta",
            "Prima Anual Total": "Prima anual total",
            "Cobertura Básica": "Cobertura Básica",
            "Coberturas Adicionales con Costo": "Coberturas adicionales con costo",
            "Frecuencia de Pago": "Frecuencia de pago",
            "Periodo de Pago de Siniestro": "Periodo de pago de siniestro",
            "I.V.A.": "I.V.A.",
            "Coaseguro": "Coaseguro",
            "Deducible": "Deducible",
            "Deducible Cero por Accidente": "Deducible Cero por Accidente",
            "Gama Hospitalaria": "Gama Hospitalaria",
            "Cobertura Nacional": "Cobertura Nacional",
            "Plazo de Pago": "Plazo de pago",
            "Número de Póliza": "Número de póliza",
            "Nombre del Plan": "Nombre del plan"
        }
        
        # Leer el archivo markdown
        with open(ruta_md, 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        # Extraer los valores con regex
        for md_key, json_key in mappings.items():
            patron = f"\\*\\*{re.escape(md_key)}\\*\\*: ([^\\n]+)"
            match = re.search(patron, contenido)
            if match:
                valor = match.group(1).strip()
                if valor != "Por determinar":
                    # Para el nombre del plan, usar directamente el valor sin prefijo
                    if json_key == "Nombre del plan":
                        resultado[json_key] = valor
                    else:
                        resultado[json_key] = valor
                        
                    logging.info(f"Extraído desde markdown: {json_key} = {resultado[json_key]}")
        
        # Si no hay fecha de fin de vigencia pero hay plazo de pago, usar ese valor
        if resultado["Fecha de fin de vigencia"] == "0" and resultado["Plazo de pago"] != "0":
            logging.info(f"No se encontró Fecha de fin de vigencia, usando Plazo de pago: {resultado['Plazo de pago']}")
            resultado["Fecha de fin de vigencia"] = resultado["Plazo de pago"]
        
        # Para este formato de póliza, el domicilio del asegurado es el mismo que el del contratante
        if resultado["Domicilio del contratante"] != "0":
            logging.info(f"Usando el mismo domicilio para asegurado y contratante: {resultado['Domicilio del contratante']}")
            resultado["Domicilio del asegurado"] = resultado["Domicilio del contratante"]
        
        # Aseguramos que "Nombre del asegurado titular" permanezca en "0" para este formato
        logging.info("Omitiendo procesamiento de 'Nombre del asegurado titular' para este formato")
        resultado["Nombre del asegurado titular"] = "0"
        
    except Exception as e:
        logging.error(f"Error extrayendo datos desde markdown: {str(e)}", exc_info=True)
    
    return resultado

def guardar_a_json(datos: Dict, ruta_salida: str) -> None:
    """
    Guarda los resultados en formato JSON
    """
    try:
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
    ruta_md = f"{nombre_base}.md"
    
    # Verificar si existe el archivo markdown, si no existe, crear uno
    if not os.path.exists(ruta_md):
        # Extraer datos del PDF
        datos = extraer_datos_poliza_vida(ruta_pdf)
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
    
    parser = argparse.ArgumentParser(description="Extractor de datos de pólizas de vida desde PDFs")
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