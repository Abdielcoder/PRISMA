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
    Detecta el tipo de documento basado en patrones específicos para pólizas Protegete Temporal MN.
    """
    # Patrones para identificar documentos Protegete Temporal MN
    if re.search(r'VIDA PROTGT TEMPORAL MN|PROTGT TEMPORAL MN|TEMPORAL MN', texto_pdf, re.IGNORECASE):
        logging.info("Detectado: Documento de Protegete Temporal MN")
        return "PROTGT_TEMPORAL_MN"
    
    # Si no coincide con ningún patrón conocido pero parece ser de vida
    if re.search(r'Temporal\s+de\s+Vida|Seguro\s+de\s+Vida|P[óo]liza\s+de\s+Vida', texto_pdf, re.IGNORECASE):
        logging.info("Detectado: Documento de Vida (formato general)")
        return "VIDA"
    
    # Si no coincide con ningún patrón conocido
    logging.warning("Tipo de documento no identificado claramente")
    return "DESCONOCIDO"

def extraer_datos_poliza_protgt_temporal_mn(pdf_path: str) -> Dict:
    """
    Extrae datos de una póliza Protegete Temporal MN desde un archivo PDF.
    """
    logging.info(f"Procesando archivo Protegete Temporal MN: {pdf_path}")
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
        if tipo_documento != "PROTGT_TEMPORAL_MN" and tipo_documento != "VIDA":
            logging.warning(f"Este documento no parece ser una póliza Protegete Temporal MN: {tipo_documento}")

        # Sistema de patrones alternativos para campos críticos
        patrones_alternativos = {
            "Suma asegurada": [
                r'(?:Cobertura básica|Fallecimiento).*?(\d{1,3}(?:,\d{3})*\.\d{2})',
                r'(?:Suma asegurada|Suma\s+Asegurada).*?(\d{1,3}(?:,\d{3})*\.\d{2})'
            ],
            "Cobertura Básica": [
                r'(?:Cobertura básica|COBERTURA BÁSICA).*?(\d+\s+(?:años|AÑOS))',
                r'Plazo.*?Seguro.*?(\d+\s+(?:años|AÑOS))'
            ]
        }

        # Patrones específicos para el formato Protegete Temporal MN
        patrones = {
            "Clave Agente": r'Agente:?\s+(\d+)|Promotor:?\s+(\d+)',
            "Nombre del agente": r'(?:Agente:?\s+\d+\s+)([A-ZÁ-Ú\s,.]+?)(?=\s+Promotor:|$)',
            "Nombre del asegurado titular": r'Datos del asegurado\s+Nombre:\s+([A-ZÁ-Ú\s,.]+?)(?=\s+Fecha|$)',
            "Nombre del contratante": r'Datos del contratante\s+Nombre:\s+([A-ZÁ-Ú\s,.]+?)(?=\s+Domicilio|$)',
            "Domicilio del contratante": r'Domicilio:\s+(.*?)(?=\s+R\.F\.C\.:|$)',
            "Código Postal": r'(?:C\.P\.|CP|[\d,]+,)\s*(\d{5})',
            "Teléfono": r'Teléfono:\s+([0-9]{7,10})',
            "R.F.C.": r'R\.F\.C\.:\s+([A-Z0-9]{10,13})',
            "Fecha de emisión": r'Fecha de emisión\s+([0-9]{1,2}/[A-Z]{3}/[0-9]{4})',
            "Fecha de inicio de vigencia": r'(?:Fecha de inicio\s+de vigencia|Fecha de inicio|Inicio de Vigencia)\s+([0-9]{1,2}/[A-Z]{3}/[0-9]{4})',
            "Fecha de fin de vigencia": r'(?:Fecha de fin\s+de vigencia|Fecha de fin|Fin de Vigencia)\s+([0-9]{1,2}/[A-Z]{3}/[0-9]{4})',
            "Plazo de pago": r'Plazo de\s+pago\s+([0-9]+\s+(?:años|AÑOS))',
            "Forma de pago": r'Forma de pago\s+([A-ZÁ-Ú]+)',
            "Frecuencia de pago": r'Forma de pago\s+([A-ZÁ-Ú]+)',  # Mismo patrón que Forma de pago
            "Nombre del plan": r'(?:VIDA PROTGT TEMPORAL MN|Tipo de Plan\s+([\w\s]+))',
            "Número de póliza": r'(?:Póliza|PÓLIZA)\s+([A-Z0-9]+H?)',
            "Prima Neta": r'Prima anual\s+([\d,]+\.\d{2})',
            "Prima anual total": r'Prima anual total\s+([\d,]+\.\d{2})',
            "Prima mensual": r'Prima\s+mensual\s+([\d,]+\.\d{2})|Según\s+Forma\s+de\s+Pago\s+([\d,]+\.\d{2})',
            "Suma asegurada": r'Básica\s+\d+\s+AÑOS\s+([\d,]+\.\d{2})',
            "Moneda": r'Moneda\s+([A-ZÁ-Ú]+)',
            "Centro de Utilidad": r'Centro de Utilidad:\s+(\d+)',
            "Cobertura Básica": r'Básica\s+(\d+\s+AÑOS)\s+[\d,]+\.\d{2}'
        }

        # Extraer valores usando patrones específicos
        for campo, patron in patrones.items():
            match = re.search(patron, texto_completo, re.MULTILINE | re.IGNORECASE)
            if match:
                if campo == "Domicilio del contratante":
                    valor = match.group(1).strip()
                    # Limpiar saltos de línea y espacios múltiples
                    valor = re.sub(r'\s*\n\s*', ' ', valor)
                    # Limitar a 50 caracteres si es necesario
                    if len(valor) > 50:
                        valor = valor[:50]
                    resultado[campo] = valor
                    logging.info(f"Domicilio extraído: {valor}")
                elif campo in ["Prima Neta", "Prima anual total", "Suma asegurada"]:
                    # Para valores numéricos, aplicamos la normalización
                    if match.groups():
                        valor = next((g for g in match.groups() if g), "").strip()
                        resultado[campo] = normalizar_numero(valor)
                    else:
                        valor = match.group(1).strip()
                        resultado[campo] = normalizar_numero(valor)
                elif campo == "Clave Agente":
                    # La clave de agente puede estar en diferentes grupos
                    if match.groups():
                        for grupo in match.groups():
                            if grupo:
                                resultado[campo] = grupo.strip()
                                break
                    else:
                        resultado[campo] = match.group(1).strip()
                else:
                    if match.groups() and len(match.groups()) > 0:
                        for grupo in match.groups():
                            if grupo:
                                resultado[campo] = grupo.strip()
                                break
                    else:
                        resultado[campo] = match.group(1).strip()
                
                if resultado[campo] != '0':
                    logging.info(f"Encontrado {campo}: {resultado[campo]}")

        # Post-procesamiento específico para Protegete Temporal MN

        # Si la Moneda es MN, asegurarnos de capturarla
        if resultado["Moneda"] == "0" and "MN" in texto_completo:
            resultado["Moneda"] = "MN"
            logging.info("Asignado Moneda: MN (detectado en texto)")

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
            # Buscar en todo el texto para encontrar el número de póliza con formato 1058047H
            poliza_match = re.search(r'(?:Póliza|PÓLIZA|Poliza)\s*[:\s]\s*(\d+[A-Z]?H?)|(\d+[A-Z]?H?)(?:\s+Este)', texto_completo)
            if poliza_match:
                # Seleccionar el grupo que no es None
                poliza_num = next((g for g in poliza_match.groups() if g), "")
                if poliza_num:
                    resultado["Número de póliza"] = poliza_num.strip()
                    logging.info(f"Número de póliza encontrado (alt): {resultado['Número de póliza']}")
            else:
                # Última posibilidad - buscar el valor de póliza en sitios comunes del documento
                poliza_lines = [line for line in texto_completo.split('\n') if 'póliza' in line.lower() or '1058047' in line]
                if poliza_lines:
                    for line in poliza_lines:
                        match = re.search(r'(\d+[A-Z]?H?)', line)
                        if match and len(match.group(1)) > 5:  # Debe ser un número suficientemente largo
                            resultado["Número de póliza"] = match.group(1).strip()
                            logging.info(f"Número de póliza encontrado (último intento): {resultado['Número de póliza']}")
                            break

        # Nombre del plan puede estar en el encabezado del documento
        if resultado["Nombre del plan"] == "0":
            # Buscar directamente el nombre del plan en el encabezado del documento
            plan_match = re.search(r'VIDA PROTGT TEMPORAL MN', texto_completo)
            if plan_match:
                resultado["Nombre del plan"] = plan_match.group(0).strip()
                logging.info(f"Nombre del plan encontrado (alt): {resultado['Nombre del plan']}")
            else:
                # Buscar cualquier mención a "Tipo de Plan"
                plan_match = re.search(r'Tipo de Plan\s+([A-ZÁ-ÚÑa-zá-úñ\s]+)', texto_completo)
                if plan_match:
                    resultado["Nombre del plan"] = plan_match.group(1).strip()
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
            # Caso específico para Protegete Temporal MN
            if "PROTGT" in texto_completo and "TEMPORAL" in texto_completo and "MN" in texto_completo:
                resultado["Nombre del plan"] = "VIDA PROTGT TEMPORAL MN"
                logging.info(f"Nombre del plan establecido por default: {resultado['Nombre del plan']}")
        
        # La cobertura básica puede estar en la sección de coberturas
        if resultado["Cobertura Básica"] == "0":
            # Buscar en la sección de coberturas
            cobertura_match = re.search(r'Básica\s+(\d+\s+AÑOS)\s+[\d,]+\.\d{2}', texto_completo)
            if cobertura_match:
                resultado["Cobertura Básica"] = cobertura_match.group(1).strip()
                logging.info(f"Cobertura básica encontrada: {resultado['Cobertura Básica']}")
        
        # El número de póliza podría ser incorrecto, buscar específicamente 1058047H
        poliza_alt_match = re.search(r'(\d{7}H)', texto_completo)
        if poliza_alt_match:
            # Este formato es más específico (7 dígitos seguidos de H)
            resultado["Número de póliza"] = poliza_alt_match.group(1).strip()
            logging.info(f"Número de póliza corregido: {resultado['Número de póliza']}")

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
            except Exception as e:
                logging.error(f"Error al calcular prima mensual: {str(e)}")

    except Exception as e:
        logging.error(f"Error procesando PDF de Protegete Temporal MN: {str(e)}", exc_info=True)

    return resultado

def generar_markdown(datos: Dict, ruta_salida: str = "protegete_temporal_mn.md") -> None:
    """
    Genera un archivo markdown con los datos extraídos estructurados para pólizas Protegete Temporal MN.
    """
    try:
        # Organizar datos por categorías
        info_general = {
            "Tipo de Documento": "Póliza Protegete Temporal MN",
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
        md_content = "# Datos Extraídos de Póliza Protegete Temporal MN\n\n"
        
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
        
        md_content += "El documento es una póliza Protegete Temporal MN. Los valores \"Por determinar\" indican campos que no pudieron ser claramente identificados en el documento original PDF."
        
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
            "Teléfono": "0", "Url": "0", "Suma asegurada": "0", "Moneda": "0"
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
    Procesa un archivo PDF de Protegete Temporal MN y guarda los resultados en markdown y JSON.
    
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
        datos = extraer_datos_poliza_protgt_temporal_mn(ruta_pdf)
        
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
    
    parser = argparse.ArgumentParser(description='Procesa archivos PDF de pólizas Protegete Temporal MN y extrae sus datos')
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
