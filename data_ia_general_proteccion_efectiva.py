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
    Detecta si el documento es una póliza de Protección Efectiva.
    """
    # Patrones para identificar documentos de Protección Efectiva
    if re.search(r'Protecci[óo]n Efectiva|Carátula de Póliza', texto_pdf, re.IGNORECASE):
        logging.info("Detectado: Documento de Protección Efectiva")
        return "PROTECCION_EFECTIVA"
    
    # Si no coincide con ningún patrón conocido
    logging.warning("Tipo de documento no identificado como Protección Efectiva")
    return "DESCONOCIDO"

def extraer_datos_poliza_proteccion_efectiva(pdf_path: str) -> Dict:
    """
    Extrae datos de una póliza de Protección Efectiva desde un archivo PDF.
    """
    logging.info(f"Procesando archivo Protección Efectiva: {pdf_path}")
    resultado = {
        "Clave Agente": "0", 
        "Promotor": "0",
        "Centro de Utilidad": "0",
        "Código Postal": "0", 
        "Domicilio del contratante": "0",
        "Fecha de emisión": "0", 
        "Fecha de fin de vigencia": "0",
        "Fecha de inicio de vigencia": "0", 
        "Forma de pago": "0",
        "Nombre del agente": "0",
        "Nombre del asegurado": "0", 
        "Nombre del contratante": "0",
        "Número de póliza": "0",
        "Edad": "0",
        "Sexo": "0",
        "Fecha de Nacimiento": "0",
        "Hábito": "0",
        "Plazo de seguro": "0",
        "Prima anual": "0", 
        "Descuento": "0", 
        "Prima anual total": "0", 
        "R.F.C.": "0",
        "Solicitud": "0",
        "Teléfono": "0", 
        "Tipo de Plan": "0",
        "Moneda": "0",
        "Incremento de Suma Asegurada": "0",
        "Prima de Incremento programado": "0",
        "Cobertura Fallecimiento": "0",
        "Cobertura Pérdida Orgánica": "0",
        "Cobertura Invalidez": "0"
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
        if tipo_documento != "PROTECCION_EFECTIVA":
            logging.warning(f"Este documento no parece ser una póliza de Protección Efectiva: {tipo_documento}")

        # Patrones específicos para el formato Protección Efectiva
        patrones = {
            "Clave Agente": r'Agente:?\s+(\d+)|Agente\s+(\d{6})',
            "Nombre del agente": r'(?:Agente:?\s+\d+\s+)([A-ZÁ-Ú\s,.]+?)(?=\s+Promotor:|$)|Agente\s+\d{6}\s+([A-ZÁ-Ú\s,.]+)',
            "Promotor": r'Promotor\s+(\d+)',
            "Centro de Utilidad": r'Centro de Utilidad\s+(\d+)',
            "Nombre del asegurado": r'Datos del asegurado\s+Nombre\s+([A-ZÁ-Ú\s,.]+?)(?=\s+Fecha|$)',
            "Nombre del contratante": r'Datos del contratante\s+Nombre\s+([A-ZÁ-Ú\s,.]+?)(?=\s+Domicilio|$)',
            "Domicilio del contratante": r'Domicilio\s+(.*?)(?=\s+R\.F\.C\.|$)',
            "Código Postal": r'(?:C\.P\.|CP|[\d,]+,)\s*(\d{5})|(\d{5}),\s+\w+',
            "Teléfono": r'Teléfono\s+([0-9]{7,10})',
            "R.F.C.": r'R\.F\.C\.\s+([A-Z0-9]{10,13})',
            "Fecha de Nacimiento": r'Fecha de Nacimiento\s+([0-9]{1,2}\s+DE\s+[A-Z]+\s+DE\s+[0-9]{4})',
            "Edad": r'Edad\s+([0-9]+)',
            "Sexo": r'Sexo\s+(FEMENINO|MASCULINO)',
            "Hábito": r'Hábito\s+(NO\s+FUMADOR|FUMADOR)',
            "Fecha de emisión": r'Fecha de emisión\s+([0-9]{1,2}/[A-Z]{3}/[0-9]{4})',
            "Fecha de inicio de vigencia": r'Fecha de inicio de vigencia\s+([0-9]{1,2}/[A-Z]{3}/[0-9]{4})',
            "Fecha de fin de vigencia": r'Fecha de fin de vigencia\s+([0-9]{1,2}/[A-Z]{3}/[0-9]{4})',
            "Plazo de seguro": r'Plazo de seguro\s+(TEMPORAL A \d+ AÑO)',
            "Forma de pago": r'Forma de pago\s+([A-ZÁ-Ú]+)',
            "Tipo de Plan": r'Tipo de Plan\s+([A-ZÁ-Ú\s]+)',
            "Número de póliza": r'Póliza\s+([A-Z0-9]+H?)',
            "Solicitud": r'Solicitud\s+([0-9]+)',
            "Moneda": r'Moneda\s+(PESOS|DÓLARES|UDIS)',
            "Incremento de Suma Asegurada": r'Incremento de Suma Asegurada\s+(.*?)(?=\n)',
            "Prima de Incremento programado": r'Prima de Incremento programado\s+(.*?)(?=\n)',
            "Prima anual": r'Prima anual\s+([\d,]+\.\d{2})',
            "Descuento": r'Descuento 10%\s+(?:-\s+)?([\d,]+\.\d{2})',
            "Prima anual total": r'Prima anual total\s+([\d,]+\.\d{2})',
            "Cobertura Fallecimiento": r'FALLECIMIENTO\s+([\d,]+\.\d{2})',
            "Cobertura Pérdida Orgánica": r'PÉRDIDA ORGÁNICA POR ACCIDENTE\s+(AMPARADO|[\d,]+\.\d{2})',
            "Cobertura Invalidez": r'INVALIDEZ TOTAL Y PERMANENTE\s+([\d,]+\.\d{2})'
        }

        # Extraer valores usando patrones específicos
        for campo, patron in patrones.items():
            match = re.search(patron, texto_completo, re.MULTILINE | re.IGNORECASE)
            if match:
                if campo == "Domicilio del contratante":
                    valor = match.group(1).strip() if match.group(1) else match.group(0).strip()
                    # Limpiar saltos de línea y espacios múltiples
                    valor = re.sub(r'\s*\n\s*', ' ', valor)
                    # Limitar a 50 caracteres si es necesario
                    if len(valor) > 50:
                        valor = valor[:50]
                    resultado[campo] = valor
                    logging.info(f"Domicilio extraído: {valor}")
                elif campo in ["Prima anual", "Descuento", "Prima anual total", "Cobertura Fallecimiento", "Cobertura Invalidez"]:
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

        # Post-procesamiento específico para Protección Efectiva

        # Si no encontramos algunos datos clave, busquemos con patrones alternativos
        if resultado["Nombre del asegurado"] == "0":
            nombre_match = re.search(r'Datos del asegurado\s+Nombre\s+(.*?)(?=\s+Fecha|\n)', texto_completo)
            if nombre_match:
                resultado["Nombre del asegurado"] = nombre_match.group(1).strip()
                logging.info(f"Nombre del asegurado encontrado (alt): {resultado['Nombre del asegurado']}")
        
        # Tratar de extraer el código postal del domicilio si no lo encontramos directamente
        if resultado["Código Postal"] == "0" and resultado["Domicilio del contratante"] != "0":
            cp_match = re.search(r'(\d{5})', resultado["Domicilio del contratante"])
            if cp_match:
                resultado["Código Postal"] = cp_match.group(1).strip()
                logging.info(f"Código postal extraído del domicilio: {resultado['Código Postal']}")
                
        # Si no encontramos la cobertura de Pérdida Orgánica como valor numérico
        if resultado["Cobertura Pérdida Orgánica"] == "0":
            # Verificar si está amparado
            amparado_match = re.search(r'PÉRDIDA ORGÁNICA POR ACCIDENTE\s+(AMPARADO)', texto_completo, re.IGNORECASE)
            if amparado_match:
                resultado["Cobertura Pérdida Orgánica"] = "AMPARADO"
                logging.info(f"Cobertura Pérdida Orgánica: AMPARADO")

    except Exception as e:
        logging.error(f"Error procesando PDF de Protección Efectiva: {str(e)}", exc_info=True)

    return resultado

def generar_markdown(datos: Dict, ruta_salida: str = "proteccion_efectiva.md") -> None:
    """
    Genera un archivo markdown con los datos extraídos estructurados para pólizas de Protección Efectiva.
    """
    try:
        # Organizar datos por categorías
        info_general = {
            "Tipo de Documento": "Póliza Protección Efectiva",
            "Número de Póliza": datos["Número de póliza"] if datos["Número de póliza"] != "0" else "Por determinar",
            "Tipo de Plan": datos["Tipo de Plan"] if datos["Tipo de Plan"] != "0" else "Por determinar",
            "Solicitud": datos["Solicitud"] if datos["Solicitud"] != "0" else "Por determinar"
        }
        
        datos_asegurado = {
            "Nombre del Asegurado": datos["Nombre del asegurado"] if datos["Nombre del asegurado"] != "0" else "Por determinar",
            "Nombre del Contratante": datos["Nombre del contratante"] if datos["Nombre del contratante"] != "0" else "Por determinar",
            "R.F.C.": datos["R.F.C."] if datos["R.F.C."] != "0" else "Por determinar",
            "Domicilio del Contratante": datos["Domicilio del contratante"] if datos["Domicilio del contratante"] != "0" else "Por determinar",
            "Código Postal": datos["Código Postal"] if datos["Código Postal"] != "0" else "Por determinar",
            "Teléfono": datos["Teléfono"] if datos["Teléfono"] != "0" else "Por determinar",
            "Fecha de Nacimiento": datos["Fecha de Nacimiento"] if datos["Fecha de Nacimiento"] != "0" else "Por determinar",
            "Edad": datos["Edad"] if datos["Edad"] != "0" else "Por determinar",
            "Sexo": datos["Sexo"] if datos["Sexo"] != "0" else "Por determinar",
            "Hábito": datos["Hábito"] if datos["Hábito"] != "0" else "Por determinar"
        }
        
        datos_agente = {
            "Clave Agente": datos["Clave Agente"] if datos["Clave Agente"] != "0" else "Por determinar",
            "Nombre del Agente": datos["Nombre del agente"] if datos["Nombre del agente"] != "0" else "Por determinar",
            "Promotor": datos["Promotor"] if datos["Promotor"] != "0" else "Por determinar",
            "Centro de Utilidad": datos["Centro de Utilidad"] if datos["Centro de Utilidad"] != "0" else "Por determinar"
        }
        
        fechas = {
            "Fecha de Emisión": datos["Fecha de emisión"] if datos["Fecha de emisión"] != "0" else "Por determinar",
            "Fecha de Inicio de Vigencia": datos["Fecha de inicio de vigencia"] if datos["Fecha de inicio de vigencia"] != "0" else "Por determinar",
            "Fecha de Fin de Vigencia": datos["Fecha de fin de vigencia"] if datos["Fecha de fin de vigencia"] != "0" else "Por determinar"
        }
        
        info_financiera = {
            "Prima Anual": datos["Prima anual"] if datos["Prima anual"] != "0" else "Por determinar",
            "Descuento": datos["Descuento"] if datos["Descuento"] != "0" else "Por determinar",
            "Prima Anual Total": datos["Prima anual total"] if datos["Prima anual total"] != "0" else "Por determinar",
            "Moneda": datos["Moneda"] if datos["Moneda"] != "0" else "Por determinar",
            "Forma de Pago": datos["Forma de pago"] if datos["Forma de pago"] != "0" else "Por determinar",
            "Plazo de Seguro": datos["Plazo de seguro"] if datos["Plazo de seguro"] != "0" else "Por determinar",
            "Incremento de Suma Asegurada": datos["Incremento de Suma Asegurada"] if datos["Incremento de Suma Asegurada"] != "0" else "Por determinar",
            "Prima de Incremento programado": datos["Prima de Incremento programado"] if datos["Prima de Incremento programado"] != "0" else "Por determinar"
        }
        
        coberturas = {
            "Cobertura Fallecimiento": datos["Cobertura Fallecimiento"] if datos["Cobertura Fallecimiento"] != "0" else "Por determinar",
            "Cobertura Pérdida Orgánica": datos["Cobertura Pérdida Orgánica"] if datos["Cobertura Pérdida Orgánica"] != "0" else "Por determinar",
            "Cobertura Invalidez": datos["Cobertura Invalidez"] if datos["Cobertura Invalidez"] != "0" else "Por determinar"
        }
        
        # Construir el markdown
        md_content = "# Datos Extraídos de Póliza Protección Efectiva\n\n"
        
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
        
        # Coberturas
        md_content += "## Coberturas\n"
        for clave, valor in coberturas.items():
            md_content += f"- **{clave}**: {valor}\n"
        md_content += "\n"
        
        md_content += "El documento es una póliza de Protección Efectiva. Los valores \"Por determinar\" indican campos que no pudieron ser claramente identificados en el documento original PDF."
        
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
    Procesa un archivo PDF de Protección Efectiva y guarda los resultados en markdown y JSON.
    
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
        datos = extraer_datos_poliza_proteccion_efectiva(ruta_pdf)
        
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
    
    parser = argparse.ArgumentParser(description='Procesa archivos PDF de pólizas Protección Efectiva y extrae sus datos')
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
