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
    Detecta si el documento es una póliza de Plan Protege PYME.
    """
    # Patrones para identificar documentos de Plan Protege PYME
    if re.search(r'PLAN PROTEGE PYME|PROTEGE PYME|Carátula de póliza[\s\S]*?PLAN PROTEGE', texto_pdf, re.IGNORECASE):
        logging.info("Detectado: Documento de Plan Protege PYME")
        return "PROTGT_PYME"
    
    # Si no coincide con ningún patrón conocido
    logging.warning("Tipo de documento no identificado como Plan Protege PYME")
    return "DESCONOCIDO"

def extraer_datos_poliza_protgt_pyme(pdf_path: str) -> Dict:
    """
    Extrae datos de una póliza de Plan Protege PYME desde un archivo PDF.
    """
    logging.info(f"Procesando archivo Plan Protege PYME: {pdf_path}")
    resultado = {
        "Clave Agente": "0", 
        "Promotor": "0",
        "Centro de Costos": "0",
        "Código Postal": "0", 
        "Domicilio del contratante": "0",
        "Fecha de emisión": "0", 
        "Fecha de fin de vigencia": "0",
        "Fecha de inicio de vigencia": "0", 
        "Forma de pago": "0",
        "Nombre del agente": "0",
        "Grupo Empresarial": "0",
        "Contratante": "0",
        "Número de póliza": "0",
        "Regla para determinar la suma asegurada": "0",
        "Características del grupo asegurado": "0",
        "Prima": "0", 
        "Recargo por pago fraccionado": "0", 
        "Prima Total": "0", 
        "R.F.C.": "0",
        "Teléfono": "0", 
        "Tipo de Plan": "0",
        "Moneda": "0",
        "Conducto de Cobro": "0",
        "SAMI": "0",
        "Pago de la Prima": "0",
        "Porcentaje de Contribución del asegurado": "0",
        "Tipo de Administración": "0",
        "Cobertura Básica": "0",
        "Edad Máxima de Aceptación": "0",
        "Integrantes": "0",
        "Suma Asegurada": "0",
        "Prima anual": "0"
    }

    try:
        # Extraer texto del PDF usando PyMuPDF para mejor manejo de layout
        doc = fitz.open(pdf_path)
        texto_completo = ""
        for page in doc:
            texto_completo += page.get_text("text", sort=True) + "\n"  # Usar sort=True para orden de lectura
        doc.close()

        # Detectar tipo de documento
        tipo_documento = detectar_tipo_documento(texto_completo)
        if tipo_documento != "PROTGT_PYME":
            logging.warning(f"Este documento no parece ser una póliza de Plan Protege PYME: {tipo_documento}")

        # Patrones específicos para el formato Plan Protege PYME
        patrones = {
            "Clave Agente": r'Agente:?\s+(\d+)|Agente\s+(\d{6})',
            "Nombre del agente": r'(?:Agente:?\s+\d+\s+)([A-ZÁ-Ú\s,.]+?)(?=\s+Promotor:|$)|Agente\s+\d{6}\s+([A-ZÁ-Ú\s,.]+)',
            "Grupo Empresarial": r'Grupo Empresarial\s+([A-ZÁ-Ú0-9\s,.]+)(?=\s+Contratante|$)',
            "Contratante": r'Contratante\s+([A-ZÁ-Ú0-9\s,.]+)(?=\s+Domicilio|$)',
            "Domicilio del contratante": r'Domicilio\s+(.*?)(?=\s+R\.F\.C\.|$)',
            "Código Postal": r'(?:C\.P\.|CP|[\d,]+,)\s*(\d{5})|(\d{5}),\s+\w+',
            "Teléfono": r'Teléfono:?\s+([0-9]{7,10})',
            "R.F.C.": r'R\.F\.C\.\s+([A-Z0-9]{10,13})',
            "Características del grupo asegurado": r'Características del grupo asegurado\s+(.*?)(?=\s+Regla para determinar|$)',
            "Regla para determinar la suma asegurada": r'Regla para determinar la suma asegurada\s+(.*?)(?=\s+Según|$)',
            "Fecha de emisión": r'Fecha de emisión\s+(\d{1,2}/\d{1,2}/\d{4})',
            "Fecha de inicio de vigencia": r'Fecha de inicio\s+de vigencia\s+(\d{1,2}/\d{1,2}/\d{4})',
            "Fecha de fin de vigencia": r'Fecha de fin\s+de vigencia\s+(\d{1,2}/\d{1,2}/\d{4})',
            "Forma de pago": r'Forma de pago\s+([A-ZÁ-Ú]+)',
            "Tipo de Plan": r'Tipo de Plan\s+([A-ZÁ-Ú\s]+)',
            "Número de póliza": r'[Pp]óliza\s+([A-Z0-9]+)',
            "Moneda": r'Moneda\s+(.*?)(?=\s+Conducto|$)',
            "Conducto de Cobro": r'Conducto de Cobro\s+(.*?)(?=\s+Forma|$)',
            "SAMI": r'SAMI\s+\$([\d,]+\.\d{2})',
            "Pago de la Prima": r'Pago de la Prima\s+(.*?)(?=\s+Porcentaje|$)',
            "Porcentaje de Contribución del asegurado": r'Porcentaje de Contribución\s+del asegurado\s+(.*?)(?=\s+Prima|$)',
            "Prima": r'Prima\s+\$([\d,]+\.\d{2})',
            "Recargo por pago fraccionado": r'Recargo por pago\s+fraccionado\s+\$([\d,]+\.\d{2})',
            "Prima Total": r'Prima Total\s+\$([\d,]+\.\d{2})',
            "Tipo de Administración": r'Tipo de Administración\s+(.*?)(?=\s+Coberturas|$)',
            "Promotor": r'Promotor\s+(\d+)',
            "Centro de Costos": r'Centro de Costos\s+(\d+)',
            "Cobertura Básica": r'BÁSICA\s+(\d+\s+años)',
            "Edad Máxima de Aceptación": r'Edad Máxima de\s+Aceptación\s+(\d+\s+años)',
            "Integrantes": r'Integrantes\s+(\d+)',
            "Suma Asegurada": r'Suma Asegurada\s+\$([\d,]+\.\d{2})',
            "Prima anual": r'Prima anual\s+\$([\d,]+\.\d{2})'
        }

        # Extraer valores usando patrones específicos
        for campo, patron in patrones.items():
            match = re.search(patron, texto_completo, re.MULTILINE | re.IGNORECASE)
            if match:
                if campo == "Domicilio del contratante":
                    valor = match.group(1).strip() if match.group(1) else match.group(0).strip()
                    # Limpiar saltos de línea y espacios múltiples
                    valor = re.sub(r'\s*\n\s*', ' ', valor)
                    resultado[campo] = valor
                    logging.info(f"Domicilio extraído: {valor}")
                elif campo in ["Prima", "Recargo por pago fraccionado", "Prima Total", "SAMI", "Suma Asegurada", "Prima anual"]:
                    # Para valores numéricos, aplicamos la normalización
                    if match.groups():
                        valor = next((g for g in match.groups() if g), "").strip()
                        resultado[campo] = normalizar_numero(valor)
                    else:
                        try:
                            valor = match.group(1).strip()
                            resultado[campo] = normalizar_numero(valor)
                        except IndexError:
                            # Si no hay group(1), intenta con group(0) que es el match completo
                            valor = match.group(0).strip()
                            resultado[campo] = normalizar_numero(valor)
                    logging.info(f"Encontrado {campo}: {resultado[campo]}")
                elif campo in ["Características del grupo asegurado", "Regla para determinar la suma asegurada"]:
                    # Para valores de texto largos
                    valor = match.group(1).strip() if match.group(1) else match.group(0).strip()
                    # Limpiar saltos de línea y espacios múltiples
                    valor = re.sub(r'\s*\n\s*', ' ', valor)
                    resultado[campo] = valor
                    logging.info(f"{campo} extraído: {valor[:50]}...")
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

        # Post-procesamiento específico para Plan Protege PYME

        # Tratar de extraer el código postal del domicilio si no lo encontramos directamente
        if resultado["Código Postal"] == "0" and resultado["Domicilio del contratante"] != "0":
            cp_match = re.search(r'CP(\d{5})|C\.P\.?\s*(\d{5})', resultado["Domicilio del contratante"], re.IGNORECASE)
            if cp_match:
                resultado["Código Postal"] = cp_match.group(1) if cp_match.group(1) else cp_match.group(2)
                logging.info(f"Código postal extraído del domicilio: {resultado['Código Postal']}")
            else:
                # Intenta buscar solo 5 dígitos seguidos
                cp_match = re.search(r'(\d{5})', resultado["Domicilio del contratante"])
                if cp_match:
                    resultado["Código Postal"] = cp_match.group(1).strip()
                    logging.info(f"Código postal extraído del domicilio (regex alternativo): {resultado['Código Postal']}")

        # Si no encontramos la cobertura básica pero tenemos otros datos de la tabla
        if resultado["Cobertura Básica"] == "0" and resultado["Suma Asegurada"] != "0":
            cobertura_match = re.search(r'BÁSICA', texto_completo, re.IGNORECASE)
            if cobertura_match:
                resultado["Cobertura Básica"] = "BÁSICA"
                logging.info(f"Cobertura Básica encontrada: BÁSICA")

        # Buscar el grupo empresarial si no lo encontramos con el patrón inicial
        if resultado["Grupo Empresarial"] == "0":
            grupo_match = re.search(r'(?:Datos del contratante|Contratante)\s+Grupo Empresarial\s+([A-ZÁ-Ú0-9\s,.]+)', texto_completo, re.IGNORECASE)
            if grupo_match:
                resultado["Grupo Empresarial"] = grupo_match.group(1).strip()
                logging.info(f"Grupo Empresarial encontrado (alt): {resultado['Grupo Empresarial']}")

    except Exception as e:
        logging.error(f"Error procesando PDF de Plan Protege PYME: {str(e)}", exc_info=True)

    return resultado

def generar_markdown(datos: Dict, ruta_salida: str = "protgt_pyme.md") -> None:
    """
    Genera un archivo markdown con los datos extraídos estructurados para pólizas de Plan Protege PYME.
    """
    try:
        # Organizar datos por categorías
        info_general = {
            "Tipo de Documento": "Plan Protege PYME",
            "Número de Póliza": datos["Número de póliza"] if datos["Número de póliza"] != "0" else "Por determinar",
            "Tipo de Plan": datos["Tipo de Plan"] if datos["Tipo de Plan"] != "0" else "Por determinar"
        }
        
        datos_contratante = {
            "Grupo Empresarial": datos["Grupo Empresarial"] if datos["Grupo Empresarial"] != "0" else "Por determinar",
            "Contratante": datos["Contratante"] if datos["Contratante"] != "0" else "Por determinar",
            "R.F.C.": datos["R.F.C."] if datos["R.F.C."] != "0" else "Por determinar",
            "Domicilio del Contratante": datos["Domicilio del contratante"] if datos["Domicilio del contratante"] != "0" else "Por determinar",
            "Código Postal": datos["Código Postal"] if datos["Código Postal"] != "0" else "Por determinar",
            "Teléfono": datos["Teléfono"] if datos["Teléfono"] != "0" else "Por determinar"
        }
        
        datos_grupo_asegurado = {
            "Características del grupo asegurado": datos["Características del grupo asegurado"] if datos["Características del grupo asegurado"] != "0" else "Por determinar",
            "Regla para determinar la suma asegurada": datos["Regla para determinar la suma asegurada"] if datos["Regla para determinar la suma asegurada"] != "0" else "Por determinar"
        }
        
        datos_agente = {
            "Clave Agente": datos["Clave Agente"] if datos["Clave Agente"] != "0" else "Por determinar",
            "Nombre del Agente": datos["Nombre del agente"] if datos["Nombre del agente"] != "0" else "Por determinar",
            "Promotor": datos["Promotor"] if datos["Promotor"] != "0" else "Por determinar",
            "Centro de Costos": datos["Centro de Costos"] if datos["Centro de Costos"] != "0" else "Por determinar"
        }
        
        fechas = {
            "Fecha de Emisión": datos["Fecha de emisión"] if datos["Fecha de emisión"] != "0" else "Por determinar",
            "Fecha de Inicio de Vigencia": datos["Fecha de inicio de vigencia"] if datos["Fecha de inicio de vigencia"] != "0" else "Por determinar",
            "Fecha de Fin de Vigencia": datos["Fecha de fin de vigencia"] if datos["Fecha de fin de vigencia"] != "0" else "Por determinar"
        }
        
        info_financiera = {
            "Prima": datos["Prima"] if datos["Prima"] != "0" else "Por determinar",
            "Recargo por pago fraccionado": datos["Recargo por pago fraccionado"] if datos["Recargo por pago fraccionado"] != "0" else "Por determinar",
            "Prima Total": datos["Prima Total"] if datos["Prima Total"] != "0" else "Por determinar",
            "Moneda": datos["Moneda"] if datos["Moneda"] != "0" else "Por determinar",
            "Conducto de Cobro": datos["Conducto de Cobro"] if datos["Conducto de Cobro"] != "0" else "Por determinar",
            "Forma de Pago": datos["Forma de pago"] if datos["Forma de pago"] != "0" else "Por determinar",
            "SAMI": datos["SAMI"] if datos["SAMI"] != "0" else "Por determinar",
            "Pago de la Prima": datos["Pago de la Prima"] if datos["Pago de la Prima"] != "0" else "Por determinar",
            "Porcentaje de Contribución del asegurado": datos["Porcentaje de Contribución del asegurado"] if datos["Porcentaje de Contribución del asegurado"] != "0" else "Por determinar",
            "Tipo de Administración": datos["Tipo de Administración"] if datos["Tipo de Administración"] != "0" else "Por determinar"
        }
        
        coberturas = {
            "Cobertura Básica": datos["Cobertura Básica"] if datos["Cobertura Básica"] != "0" else "Por determinar",
            "Edad Máxima de Aceptación": datos["Edad Máxima de Aceptación"] if datos["Edad Máxima de Aceptación"] != "0" else "Por determinar",
            "Integrantes": datos["Integrantes"] if datos["Integrantes"] != "0" else "Por determinar",
            "Suma Asegurada": datos["Suma Asegurada"] if datos["Suma Asegurada"] != "0" else "Por determinar",
            "Prima anual": datos["Prima anual"] if datos["Prima anual"] != "0" else "Por determinar"
        }
        
        # Construir el markdown
        md_content = "# Datos Extraídos de Plan Protege PYME\n\n"
        
        # Información General
        md_content += "## Información General\n"
        for clave, valor in info_general.items():
            md_content += f"- **{clave}**: {valor}\n"
        md_content += "\n"
        
        # Datos del Contratante
        md_content += "## Datos del Contratante\n"
        for clave, valor in datos_contratante.items():
            md_content += f"- **{clave}**: {valor}\n"
        md_content += "\n"
        
        # Datos del Grupo Asegurado
        md_content += "## Datos del Grupo Asegurado\n"
        for clave, valor in datos_grupo_asegurado.items():
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
        
        # Coberturas
        md_content += "## Coberturas\n"
        for clave, valor in coberturas.items():
            md_content += f"- **{clave}**: {valor}\n"
        md_content += "\n"
        
        md_content += "El documento es un Plan Protege PYME. Los valores \"Por determinar\" indican campos que no pudieron ser claramente identificados en el documento original PDF."
        
        # Guardar el archivo markdown
        with open(ruta_salida, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logging.info(f"Archivo markdown generado en {ruta_salida}")
        
    except Exception as e:
        logging.error(f"Error generando archivo markdown: {str(e)}", exc_info=True)

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
    Procesa un archivo PDF de Plan Protege PYME y guarda los resultados en markdown y JSON.
    
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
        datos = extraer_datos_poliza_protgt_pyme(ruta_pdf)
        
        # Generar archivos de salida
        generar_markdown(datos, ruta_md)
        guardar_a_json(datos, ruta_json)
        
        # Guardar la ruta del archivo markdown para referencia
        datos["file_path"] = ruta_md
        
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
    
    parser = argparse.ArgumentParser(description='Procesa archivos PDF de pólizas Plan Protege PYME y extrae sus datos')
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
