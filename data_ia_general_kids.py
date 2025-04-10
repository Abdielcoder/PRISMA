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
    la consistencia con los otros formatos
    """
    if not valor:
        return "0"
    
    # Elimina espacios y caracteres no deseados pero mantiene comas y puntos
    valor = re.sub(r'[$\s]', '', valor)
    
    # Quita comas usadas como separadores de miles antes de la conversión
    valor = valor.replace(',', '')
    
    # Asegura que tenga dos decimales si es un número flotante
    try:
        float_val = float(valor)
        return f"{float_val:.2f}"
    except ValueError:
        # Si no se puede convertir a float, devolver el valor limpio
        return valor

def detectar_tipo_documento(texto: str) -> str:
    """
    Detecta si el documento es de tipo ALIADOS+ KIDS.
    
    Args:
        texto (str): Texto extraído del PDF
        
    Returns:
        str: Tipo de documento detectado
    """
    # Normalizar el texto
    texto = texto.lower()
    texto = re.sub(r'\s+', ' ', texto)
    
    # Patrones para identificar ALIADOS+ KIDS
    patrones_kids = [
        r"aliados\+\s*kids",
        r"aliados\s+kids",
        r"carátula de póliza.*aliados.*kids",
        r"aliados.*kids.*carátula",
        r"póliza.*aliados.*kids",
        r"datos del asegurado menor",
        r"aliados\+ kids"
    ]
    
    # Contar cuántos patrones coinciden
    coincidencias = sum(1 for pattern in patrones_kids if re.search(pattern, texto))
    
    # Si más del 40% de los patrones coinciden, consideramos que es el documento correcto
    if coincidencias >= len(patrones_kids) * 0.4:
        logging.info(f"Detectado documento de tipo ALIADOS_KIDS con {coincidencias} coincidencias")
        return "ALIADOS_KIDS"
    
    logging.info(f"No se detectó documento de tipo ALIADOS_KIDS (solo {coincidencias} coincidencias)")
    return "DESCONOCIDO"

def extraer_datos_poliza_aliados_kids(pdf_path: str) -> Dict:
    """
    Extrae datos de una póliza de ALIADOS+ KIDS desde un archivo PDF.
    """
    logging.info(f"Procesando archivo ALIADOS+ KIDS: {pdf_path}")
    resultado = {
        "Clave Agente": "0", 
        "Promotor": "0",
        "Código Postal": "0", 
        "Domicilio del contratante": "0",
        "Ciudad del contratante": "0",
        "Fecha de emisión": "0", 
        "Fecha de fin de vigencia": "0",
        "Fecha de inicio de vigencia": "0", 
        "Frecuencia de pago": "0",
        "Tipo de pago": "0",
        "Nombre del agente": "0",
        "Nombre del contratante": "0",
        "Nombre del asegurado titular": "0",
        "Domicilio del asegurado": "0",
        "Ciudad del asegurado": "0",
        "Número de póliza": "0",
        "Solicitud": "0",
        "Tipo de Plan": "0",
        "R.F.C.": "0",
        "Teléfono": "0", 
        "Moneda": "0",
        "Prima Neta": "0",
        "Prima anual total": "0",
        "I.V.A.": "0",
        "Prima trimestral": "0",
        "Prima trimestral Total": "0",
        "Prima trimestral adicional": "0",
        "Recargo por pago fraccionado": "0",
        "Suma asegurada": "0",
        "Fecha de nacimiento": "0",
        "Edad": "0",
        "Sexo": "0",
        "Hábito": "0",
        "Plazo de seguro": "0",
        "Plazo de pago": "0",
        "Forma de pago": "0",
        "Incremento de suma asegurada": "0",
        "Prima de incremento programado": "0",
        "Centro de Utilidad": "0"
    }

    # Inicializar lista para coberturas
    coberturas_amparadas = []

    try:
        # Extraer texto del PDF usando PyMuPDF para mejor manejo de layout
        doc = fitz.open(pdf_path)
        texto_completo = ""
        texto_completo_raw = ""
        for page in doc:
            texto_completo += page.get_text("text", sort=True) + "\n"  # Usar sort=True para orden de lectura
            texto_completo_raw += page.get_text() + "\n"  # Sin ordenar para capturar texto tal como está
        doc.close()

        # --- Sección de patrones para extracción ---
        
        # Patrones para póliza y solicitud
        poliza_pattern = r'PÓLIZA\s*\n?\s*([0-9A-Z]+)'
        solicitud_pattern = r'SOLICITUD\s*\n?\s*(\d+)'
        tipo_plan_pattern = r'TIPO DE PLAN\s*\n?\s*([A-Za-z]+)'

        # Patrones para fechas
        fecha_inicio_pattern = r'Inicio de vigencia\s*\n?\s*(\d{2}/[A-Z]{3}/\d{4})'
        fecha_fin_pattern = r'Fin de vigencia\s*\n?\s*(\d{2}/[A-Z]{3}/\d{4})'
        fecha_emision_pattern = r'Fecha de emisión\s*\n?\s*(\d{2}/[A-Z]{3}/\d{4})'
        
        # Patrones para datos del contratante
        contratante_nombre_pattern = r'(?:DATOS DEL CONTRATANTE|Nombre:)\s*\n?\s*([A-ZÁ-Ú\s,.]+)'
        contratante_domicilio_pattern = r'Domicilio:\s*([^R\n]*)'
        contratante_rfc_pattern = r'R\.F\.C\.:\s*([A-Z0-9]{10,13})'
        contratante_telefono_pattern = r'Teléfono:\s*(\d+)'
        
        # Patrones para datos del asegurado menor
        asegurado_nombre_pattern = r'(?:DATOS DEL ASEGURADO MENOR|Nombre:)\s*\n?\s*([A-ZÁ-Ú\s,.]+)'
        asegurado_fecha_nac_pattern = r'Fecha de nacimiento:\s*([^E\n]*)'
        asegurado_edad_pattern = r'Edad:\s*(\d+)'
        asegurado_sexo_pattern = r'Sexo:\s*([A-Za-z]+)'
        
        # Patrones agente y promotor
        agente_pattern = r'Agente:\s*(\d+)\s+([A-ZÁ-Ú\s,.]+)'
        promotor_pattern = r'Promotor:\s*(\d+)'
        centro_utilidad_pattern = r'Centro de Utilidad:\s*(\d+)'
        
        # Patrones datos financieros
        moneda_pattern = r'Moneda\s*\n?\s*([A-Z]+)'
        prima_trimestral_pattern = r'Prima\s+trimestral\s*:\s*([\d,.]+)'
        recargo_pattern = r'Recargo por pago fraccionado\s*\n?\s*([\d,.]+)'
        prima_trim_adicional_pattern = r'Prima trimestral adicional:\s*([\d,.]+)'
        prima_anual_pattern = r'Prima anual total:\s*([\d,.]+)'
        prima_trim_total_pattern = r'Prima trimestral Total\s*\n?\s*([\d,.]+)'
        
        # Patrones para plazo y forma de pago
        plazo_seguro_pattern = r'Plazo de seguro\s+Edad alcanzada\s+(\d+)'
        plazo_pago_pattern = r'Plazo de pago\s*\n?\s*(\d+\s*(?:Años|años))'
        forma_pago_pattern = r'Forma de pago\s*\n?\s*([A-Za-z\s]+)'
        
        # Patrones para coberturas
        cobertura_pattern = r'(Aliados\+ Kids \d+|Pago Adicional por Fallecimiento \d+|Pago Adicional por Invalidez|Exención por Fallecimiento o Invalidez)\s*(\d+\s*AÑOS)\s*([\d,.]+)\s*([\d,.]+)\s*([\d,.]+)'
        
        # Diccionario con todos los patrones a buscar
        patterns = {
            "Número de póliza": poliza_pattern,
            "Solicitud": solicitud_pattern,
            "Tipo de Plan": tipo_plan_pattern,
            "Fecha de inicio de vigencia": fecha_inicio_pattern,
            "Fecha de fin de vigencia": fecha_fin_pattern,
            "Fecha de emisión": fecha_emision_pattern,
            "Nombre del contratante": contratante_nombre_pattern,
            "Domicilio del contratante": contratante_domicilio_pattern,
            "R.F.C.": contratante_rfc_pattern,
            "Teléfono": contratante_telefono_pattern,
            "Nombre del asegurado titular": asegurado_nombre_pattern,
            "Fecha de nacimiento": asegurado_fecha_nac_pattern,
            "Edad": asegurado_edad_pattern,
            "Sexo": asegurado_sexo_pattern,
            "Moneda": moneda_pattern,
            "Prima trimestral": prima_trimestral_pattern,
            "Recargo por pago fraccionado": recargo_pattern,
            "Prima trimestral adicional": prima_trim_adicional_pattern,
            "Prima anual total": prima_anual_pattern,
            "Prima trimestral Total": prima_trim_total_pattern,
            "Plazo de seguro": plazo_seguro_pattern,
            "Plazo de pago": plazo_pago_pattern,
            "Forma de pago": forma_pago_pattern
        }
        
        # --- Sección de extracción de datos ---
        # Buscar coincidencias para todos los patrones
        for campo, patron in patterns.items():
            match = re.search(patron, texto_completo, re.IGNORECASE | re.MULTILINE)
            if match:
                try:
                    if campo in ["Prima trimestral", "Prima anual total", "Prima trimestral Total", "Prima trimestral adicional", "Recargo por pago fraccionado"]:
                        valor = match.group(1).strip()
                        resultado[campo] = normalizar_numero(valor)
                    else:
                        resultado[campo] = match.group(1).strip()
                    logging.info(f"Extraído {campo}: {resultado[campo]}")
                except (IndexError, AttributeError) as e:
                    logging.warning(f"Error extrayendo {campo}: {e}")
        
        # Extraer Agente y Nombre del agente (patrón especial que extrae ambos)
        agente_match = re.search(agente_pattern, texto_completo, re.IGNORECASE)
        if agente_match:
            resultado["Clave Agente"] = agente_match.group(1).strip()
            resultado["Nombre del agente"] = agente_match.group(2).strip()
            logging.info(f"Extraído Clave Agente: {resultado['Clave Agente']}")
            logging.info(f"Extraído Nombre del agente: {resultado['Nombre del agente']}")
        
        # Extraer Promotor
        promotor_match = re.search(promotor_pattern, texto_completo, re.IGNORECASE)
        if promotor_match:
            resultado["Promotor"] = promotor_match.group(1).strip()
            logging.info(f"Extraído Promotor: {resultado['Promotor']}")
        
        # Extraer Centro de Utilidad
        centro_match = re.search(centro_utilidad_pattern, texto_completo, re.IGNORECASE)
        if centro_match:
            resultado["Centro de Utilidad"] = centro_match.group(1).strip()
            logging.info(f"Extraído Centro de Utilidad: {resultado['Centro de Utilidad']}")
        
        # Extraer coberturas amparadas
        coberturas_matches = re.finditer(cobertura_pattern, texto_completo, re.IGNORECASE | re.MULTILINE)
        for match in coberturas_matches:
            cobertura = {
                "Nombre": match.group(1).strip(),
                "Plazo": match.group(2).strip(),
                "Suma Asegurada": match.group(3).strip(),
                "Extraprima": match.group(4).strip() if match.group(4) else "0.00",
                "Prima anual": match.group(5).strip() if match.group(5) else "0.00"
            }
            coberturas_amparadas.append(cobertura)
            logging.info(f"Extraída cobertura: {cobertura['Nombre']}")
            
            # Para la primera cobertura, guardar su suma asegurada como la principal
            if resultado["Suma asegurada"] == "0" and "Aliados+ Kids" in cobertura["Nombre"]:
                resultado["Suma asegurada"] = cobertura["Suma Asegurada"]
                logging.info(f"Asignada Suma asegurada principal: {resultado['Suma asegurada']}")
        
        # Calcular Prima Neta si no se encontró directamente
        if resultado["Prima Neta"] == "0" and resultado["Prima anual total"] != "0" and resultado["I.V.A."] == "0":
            # Para pólizas de vida, la Prima Neta es igual a la Prima Total (no hay IVA)
            resultado["Prima Neta"] = resultado["Prima anual total"]
            logging.info(f"Calculada Prima Neta: {resultado['Prima Neta']}")
        
        # Añadir ciudad del contratante si hay código postal o domicilio
        if resultado["Ciudad del contratante"] == "0" and resultado["Domicilio del contratante"] != "0":
            # Intentar extraer ciudad del domicilio
            domicilio = resultado["Domicilio del contratante"]
            ciudad_match = re.search(r',\s*([A-ZÁ-Ú\s]+),', domicilio)
            if ciudad_match:
                resultado["Ciudad del contratante"] = ciudad_match.group(1).strip()
                logging.info(f"Extraída Ciudad del contratante del domicilio: {resultado['Ciudad del contratante']}")
        
        # Añadir las coberturas al resultado
        resultado["Coberturas Amparadas"] = coberturas_amparadas
        
        # Añadir URL para condiciones generales
        resultado["Url"] = "https://rinoapps.com/condiciones/aliados_kids.pdf"
    
    except Exception as e:
        logging.error(f"Error procesando PDF de ALIADOS+ KIDS: {str(e)}", exc_info=True)
    
    # Asegurar que valores numéricos tengan el formato correcto
    for campo in ["Prima Neta", "Prima anual total", "Prima trimestral", "Prima trimestral Total", "Prima trimestral adicional", "Recargo por pago fraccionado"]:
        if resultado[campo] == "0":
            resultado[campo] = "0.00"
    
    return resultado

def generar_markdown(datos: Dict, ruta_salida: str = "aliados_kids.md") -> None:
    """
    Genera un archivo markdown con los datos extraídos estructurados.
    """
    try:
        # Organizar datos por categorías
        info_general = {
            "Tipo de Documento": "Póliza ALIADOS+ KIDS",
            "Número de Póliza": datos["Número de póliza"] if datos["Número de póliza"] != "0" else "Por determinar",
            "Solicitud": datos["Solicitud"] if datos["Solicitud"] != "0" else "Por determinar",
            "Tipo de Plan": datos["Tipo de Plan"] if datos["Tipo de Plan"] != "0" else "Por determinar",
            "Moneda": datos["Moneda"] if datos["Moneda"] != "0" else "Por determinar"
        }
        
        datos_contratante = {
            "Nombre del Contratante": datos["Nombre del contratante"] if datos["Nombre del contratante"] != "0" else "Por determinar",
            "Domicilio": datos["Domicilio del contratante"] if datos["Domicilio del contratante"] != "0" else "Por determinar",
            "Ciudad": datos["Ciudad del contratante"] if datos["Ciudad del contratante"] != "0" else "Por determinar",
            "R.F.C.": datos["R.F.C."] if datos["R.F.C."] != "0" else "Por determinar",
            "Teléfono": datos["Teléfono"] if datos["Teléfono"] != "0" else "Por determinar"
        }
        
        datos_asegurado = {
            "Nombre del Asegurado": datos["Nombre del asegurado titular"] if datos["Nombre del asegurado titular"] != "0" else "Por determinar",
            "Fecha de Nacimiento": datos["Fecha de nacimiento"] if datos["Fecha de nacimiento"] != "0" else "Por determinar",
            "Edad": datos["Edad"] if datos["Edad"] != "0" else "Por determinar",
            "Sexo": datos["Sexo"] if datos["Sexo"] != "0" else "Por determinar"
        }
        
        fechas = {
            "Fecha de Emisión": datos["Fecha de emisión"] if datos["Fecha de emisión"] != "0" else "Por determinar",
            "Fecha de Inicio de Vigencia": datos["Fecha de inicio de vigencia"] if datos["Fecha de inicio de vigencia"] != "0" else "Por determinar",
            "Fecha de Fin de Vigencia": datos["Fecha de fin de vigencia"] if datos["Fecha de fin de vigencia"] != "0" else "Por determinar"
        }
        
        condiciones = {
            "Suma Asegurada": datos["Suma asegurada"] if datos["Suma asegurada"] != "0" else "Por determinar",
            "Plazo de Seguro": datos["Plazo de seguro"] if datos["Plazo de seguro"] != "0" else "Por determinar",
            "Plazo de Pago": datos["Plazo de pago"] if datos["Plazo de pago"] != "0" else "Por determinar",
            "Forma de Pago": datos["Forma de pago"] if datos["Forma de pago"] != "0" else "Por determinar"
        }
        
        info_financiera = {
            "Prima Neta": datos["Prima Neta"] if datos["Prima Neta"] != "0" else "Por determinar",
            "Prima Anual Total": datos["Prima anual total"] if datos["Prima anual total"] != "0" else "Por determinar",
            "Prima Trimestral": datos["Prima trimestral"] if datos["Prima trimestral"] != "0" else "Por determinar",
            "Recargo por Pago Fraccionado": datos["Recargo por pago fraccionado"] if datos["Recargo por pago fraccionado"] != "0" else "Por determinar",
            "Prima Trimestral Adicional": datos["Prima trimestral adicional"] if datos["Prima trimestral adicional"] != "0" else "Por determinar",
            "Prima Trimestral Total": datos["Prima trimestral Total"] if datos["Prima trimestral Total"] != "0" else "Por determinar"
        }
        
        agente_info = {
            "Clave Agente": datos["Clave Agente"] if datos["Clave Agente"] != "0" else "Por determinar",
            "Nombre del Agente": datos["Nombre del agente"] if datos["Nombre del agente"] != "0" else "Por determinar",
            "Promotor": datos["Promotor"] if datos["Promotor"] != "0" else "Por determinar",
            "Centro de Utilidad": datos["Centro de Utilidad"] if datos["Centro de Utilidad"] != "0" else "Por determinar"
        }
        
        # Construir el markdown
        md_content = "# Datos Extraídos de Póliza ALIADOS+ KIDS\n\n"
        
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
        
        # Datos del Asegurado
        md_content += "## Datos del Asegurado\n"
        for clave, valor in datos_asegurado.items():
            md_content += f"- **{clave}**: {valor}\n"
        md_content += "\n"
        
        # Información de Fechas
        md_content += "## Información de Fechas\n"
        for clave, valor in fechas.items():
            md_content += f"- **{clave}**: {valor}\n"
        md_content += "\n"
        
        # Condiciones
        md_content += "## Condiciones\n"
        for clave, valor in condiciones.items():
            md_content += f"- **{clave}**: {valor}\n"
        md_content += "\n"
        
        # Información Financiera
        md_content += "## Información Financiera\n"
        for clave, valor in info_financiera.items():
            md_content += f"- **{clave}**: {valor}\n"
        md_content += "\n"
        
        # Información del Agente
        md_content += "## Información del Agente\n"
        for clave, valor in agente_info.items():
            md_content += f"- **{clave}**: {valor}\n"
        md_content += "\n"
        
        # Coberturas Amparadas
        md_content += "## Coberturas Amparadas\n"
        if "Coberturas Amparadas" in datos and datos["Coberturas Amparadas"]:
            for cobertura in datos["Coberturas Amparadas"]:
                md_content += f"- **{cobertura['Nombre']}**\n"
                md_content += f"  - Plazo: {cobertura['Plazo']}\n"
                md_content += f"  - Suma Asegurada: {cobertura['Suma Asegurada']}\n"
                md_content += f"  - Extraprima: {cobertura['Extraprima']}\n"
                md_content += f"  - Prima anual: {cobertura['Prima anual']}\n"
        else:
            md_content += "No se encontraron coberturas específicas.\n"
        md_content += "\n"
        
        md_content += "Este documento es una póliza de ALIADOS+ KIDS. Los valores \"Por determinar\" indican campos que no pudieron ser claramente identificados en el documento original PDF."
        
        # Guardar el archivo markdown
        with open(ruta_salida, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logging.info(f"Archivo markdown generado en {ruta_salida}")
        
    except Exception as e:
        logging.error(f"Error generando archivo markdown: {str(e)}", exc_info=True)

def guardar_a_json(datos: Dict, ruta_salida: str = "aliados_kids.json") -> None:
    """
    Guarda los datos extraídos en formato JSON.
    """
    try:
        with open(ruta_salida, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=4)
        logging.info(f"Archivo JSON generado en {ruta_salida}")
    except Exception as e:
        logging.error(f"Error generando archivo JSON: {str(e)}", exc_info=True)

def procesar_archivo(ruta_pdf: str, directorio_salida: str = "output") -> Dict:
    """
    Procesa un archivo PDF de ALIADOS+ KIDS y guarda los resultados en markdown y JSON.
    
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
        datos = extraer_datos_poliza_aliados_kids(ruta_pdf)
        
        # Generar archivos de salida
        generar_markdown(datos, ruta_md)
        guardar_a_json(datos, ruta_json)
        
        # Guardar la ruta del archivo markdown para referencia
        datos["file_path"] = ruta_md
        
        return datos
    except Exception as e:
        logging.error(f"Error procesando archivo {ruta_pdf}: {str(e)}", exc_info=True)
        return {}

if __name__ == "__main__":
    # Si se ejecuta el script directamente, procesar el archivo pasado como argumento
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        directorio_salida = "output"
        if len(sys.argv) > 2:
            directorio_salida = sys.argv[2]
        
        datos = procesar_archivo(pdf_path, directorio_salida)
        print(json.dumps(datos, ensure_ascii=False, indent=4))
    else:
        print("Uso: python data_ia_general_kids.py <ruta_pdf> [directorio_salida]") 