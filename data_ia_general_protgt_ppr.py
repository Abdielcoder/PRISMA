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
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename
import tempfile
import requests

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

def detect_document_type(text: str) -> str:
    """
    Detecta el tipo de documento basado en el contenido del texto.
    """
    # Normalizar el texto
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    
    # Patrones para identificar Aliados+ PPR (con alta prioridad)
    patrones_aliados_ppr = [
        r"aliados\+\s*ppr",
        r"vida y ahorro",
        r"carátula de póliza.*aliados",
        r"aliados\+.*car[áa]tula"
    ]
    
    # Primero buscar patrones de Aliados+ PPR 
    for patron in patrones_aliados_ppr:
        if re.search(patron, text):
            logger.info(f"Detectada póliza Aliados+ PPR con patrón: {patron}")
            return "ALIADOS_PPR"
            
    # Resto de patrones para otros tipos de documentos...

def extraer_datos_poliza_aliados_ppr(pdf_path: str) -> Dict:
    """
    Extrae datos de una póliza Aliados+ PPR desde un archivo PDF.
    """
    logging.info(f"Procesando archivo Aliados+ PPR: {pdf_path}")
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
        tipo_documento = detect_document_type(texto_completo)
        if tipo_documento != "ALIADOS_PPR" and tipo_documento != "VIDA":
            logging.warning(f"Este documento no parece ser una póliza Aliados+ PPR: {tipo_documento}")

        # Patrones específicos para el formato Aliados+ PPR
        patrones = {
            "Número de póliza": r'PÓLIZA\s+([0-9]{7}H)',
            "Tipo de plan": r'TIPO DE PLAN\s+(\w+)',
            "Solicitud": r'SOLICITUD\s+(\d+)',
            "Fecha de inicio de vigencia": r'Inicio de Vigencia:?\s+(\d{1,2}/\w{3}/\d{4})',
            "Fecha de fin de vigencia": r'Fin de Vigencia:?\s+(\d{1,2}/\w{3}/\d{4})',
            "Fecha de emisión": r'Fecha de Emisión:?\s+(\d{1,2}/\w{3}/\d{4})',
            "Moneda": r'Moneda:?\s+(\w+)',
            "Plazo de Seguro": r'Plazo de Seguro:?\s+(.*?)(?=\n|Plazo de Pago)',
            "Plazo de pago": r'Plazo de Pago:?\s+(\d+\s+años)',
            "Forma de pago": r'Forma de Pago:?\s+(\w+)',
            "Prima Neta": r'Prima anual\s+:\s+([\d,]+\.\d{2})',
            "Prima anual total": r'Prima Anual Total:\s+([\d,]+\.\d{2})',
            "Nombre del contratante": r'DATOS DEL CONTRATANTE\s+Nombre:\s+([A-ZÁ-Ú\s,.]+?)(?=\s+Domicilio:)',
            "Domicilio del contratante": r'Domicilio:\s+([A-ZÁ-Ú0-9,.\s]+)(?=\s+R\.F\.C\.:|$)',
            "R.F.C.": r'R\.F\.C\.:\s+([A-Z0-9]{10,13})',
            "Teléfono": r'Teléfono:\s+(\d+)',
            "Nombre del asegurado titular": r'DATOS DEL ASEGURADO\s+Nombre:\s+([A-ZÁ-Ú\s,.]+?)(?=\s+Fecha|$)',
            "Clave Agente": r'Agente:\s+(\d+)',
            "Nombre del agente": r'Agente:\s+\d+\s+([A-ZÁ-Ú\s,.]+?)(?=\s+Promotor:|$)',
            "Suma asegurada": r'SUMA\s+ASEGURADA\s+(\d{1,3}(?:,\d{3})*\.\d{2})|Básica\s+\d+\s+(?:años|AÑOS)\s+(\d{1,3}(?:,\d{3})*\.\d{2})',
            "Cobertura Básica": r'Básica\s+(\d+\s+AÑOS)|Fallecimiento\s+(\d+\s+AÑOS)',
            "Código Postal": r'C\.P\.\s+(\d{5})|,\s+(\d{5}),',
        }

        # Extraer valores usando patrones
        for campo, patron in patrones.items():
            match = re.search(patron, texto_completo, re.MULTILINE | re.IGNORECASE)
            if match:
                if campo == "Domicilio del contratante":
                    # Capturar el texto completo del domicilio y limpiarlo
                    valor = match.group(1).strip()
                    # Limpiar saltos de línea y espacios múltiples
                    valor = re.sub(r'\s*\n\s*', ' ', valor)
                    
                    # Extraer código postal del domicilio si está presente
                    cp_match = re.search(r'(\d{5})', valor)
                    if cp_match and resultado["Código Postal"] == "0":
                        resultado["Código Postal"] = cp_match.group(1)
                        logging.info(f"Código postal extraído del domicilio: {resultado['Código Postal']}")
                    
                    # Limitar a 50 caracteres si es necesario
                    if len(valor) > 50:
                        valor = valor[:50]
                    
                    resultado[campo] = valor
                    logging.info(f"Domicilio extraído: {valor}")
                elif campo in ["Prima Neta", "Prima anual total", "Suma asegurada"]:
                    # Para valores numéricos, aplicamos la normalización
                    valor = match.group(1).strip()
                    resultado[campo] = normalizar_numero(valor)
                    logging.info(f"Encontrado {campo}: {resultado[campo]}")
                elif campo == "Código Postal":
                    # Extraer código postal que puede estar en diferentes grupos
                    if match.group(1):
                        resultado[campo] = match.group(1)
                    elif len(match.groups()) > 1 and match.group(2):
                        resultado[campo] = match.group(2)
                    else:
                        resultado[campo] = match.group(0).strip()
                    logging.info(f"Encontrado {campo}: {resultado[campo]}")
                else:
                    # Verificar si existen grupos capturados antes de acceder a ellos
                    if match.groups() and len(match.groups()) > 0:
                        # Encontrar el primer grupo que no sea None
                        for grupo in match.groups():
                            if grupo is not None:
                                resultado[campo] = grupo.strip()
                                break
                        # Si no se encontró ningún grupo válido, usar el match completo
                        if resultado[campo] == "0":
                            resultado[campo] = match.group(0).strip()
                            logging.warning(f"No se encontró grupo de captura para {campo}, usando match completo")
                    else:
                        # Si no hay grupos, usar el match completo
                        resultado[campo] = match.group(0).strip()
                        logging.warning(f"No se encontró grupo de captura para {campo}, usando match completo")

        # Post-procesamiento específico para Aliados PPR

        # Para los nombres, intentar extraerlos con patrones alternativos si no se encontraron
        if resultado["Nombre del contratante"] == "0":
            nombre_contratante_match = re.search(r'(?:Nombre|DATOS DEL CONTRATANTE)[:.\s]+([A-ZÁ-Ú\s,]+?)(?=\s+Domicilio:|$)', texto_completo, re.IGNORECASE)
            if nombre_contratante_match:
                resultado["Nombre del contratante"] = nombre_contratante_match.group(1).strip()
                # Limpiar texto adicional
                resultado["Nombre del contratante"] = re.sub(r'\s+TIPO DE PLAN.*$', '', resultado["Nombre del contratante"])
                logging.info(f"Nombre del contratante encontrado (alt): {resultado['Nombre del contratante']}")
        
        if resultado["Nombre del asegurado titular"] == "0":
            # Si no se encontró el asegurado, intentar con otro patrón o usar el contratante
            nombre_asegurado_match = re.search(r'(?:DATOS DEL ASEGURADO|Asegurado)[:\s]+Nombre:\s+([A-ZÁ-Ú\s,]+)', texto_completo, re.IGNORECASE)
            if nombre_asegurado_match:
                resultado["Nombre del asegurado titular"] = nombre_asegurado_match.group(1).strip()
                # Limpiar texto adicional
                resultado["Nombre del asegurado titular"] = re.sub(r'\s+TIPO DE PLAN.*$', '', resultado["Nombre del asegurado titular"])
                logging.info(f"Nombre del asegurado encontrado (alt): {resultado['Nombre del asegurado titular']}")
            elif resultado["Nombre del contratante"] != "0":
                # Usar el nombre del contratante como asegurado si no se encontró
                resultado["Nombre del asegurado titular"] = resultado["Nombre del contratante"]
                logging.info(f"Usando el mismo nombre para asegurado y contratante: {resultado['Nombre del contratante']}")
        else:
            # Limpiar texto adicional del asegurado si ya fue encontrado
            resultado["Nombre del asegurado titular"] = re.sub(r'\s+TIPO DE PLAN.*$', '', resultado["Nombre del asegurado titular"])
            logging.info(f"Nombre del asegurado limpiado: {resultado['Nombre del asegurado titular']}")

        # Limpiar texto adicional del contratante si ya fue encontrado
        if resultado["Nombre del contratante"] != "0":
            resultado["Nombre del contratante"] = re.sub(r'\s+TIPO DE PLAN.*$', '', resultado["Nombre del contratante"])
            logging.info(f"Nombre del contratante limpiado: {resultado['Nombre del contratante']}")

        # Intentar obtener el nombre del agente nuevamente si no se encontró
        if resultado["Nombre del agente"] == "0" and resultado["Clave Agente"] != "0":
            nombre_agente_match = re.search(f'Agente:\\s+{re.escape(resultado["Clave Agente"])}\\s+([A-ZÁ-Ú\\s,.]+?)(?=\\s+Promotor:|\\s+Centro|\\s+Prima|\\s+Fracci|$)', texto_completo)
            if nombre_agente_match:
                resultado["Nombre del agente"] = nombre_agente_match.group(1).strip()
                logging.info(f"Nombre del agente encontrado (con clave): {resultado['Nombre del agente']}")

        # Limpia el nombre del agente de cualquier texto adicional
        if resultado["Nombre del agente"] != "0":
            resultado["Nombre del agente"] = re.sub(r'\s+(?:Fraccionado|Prima|Centro).*$', '', resultado["Nombre del agente"])
            logging.info(f"Nombre del agente limpiado: {resultado['Nombre del agente']}")

        # Extraer suma asegurada directamente de la tabla de coberturas
        if resultado["Suma asegurada"] == "0":
            # Buscar en la tabla de coberturas
            suma_asegurada_match = re.search(r'Fallecimiento\s+(\d{1,3}(?:,\d{3})*\.\d{2})', texto_completo)
            if suma_asegurada_match:
                resultado["Suma asegurada"] = normalizar_numero(suma_asegurada_match.group(1))
                logging.info(f"Suma asegurada encontrada (tabla): {resultado['Suma asegurada']}")
            else:
                # Buscar patrones alternativos para la suma asegurada
                suma_alt_match = re.search(r'(?:SUMA\s+ASEGURADA|SUMA ASEGURADA\s+PRIMA)|(?:Básica\s+\d+\s+AÑOS)\s+(\d{1,3}(?:,\d{3})*\.\d{2})', texto_completo, re.IGNORECASE)
                if suma_alt_match:
                    resultado["Suma asegurada"] = normalizar_numero(suma_alt_match.group(1))
                    logging.info(f"Suma asegurada encontrada (alternativa): {resultado['Suma asegurada']}")
                else:
                    # Buscar específicamente en la línea de cobertura de fallecimiento
                    lineas = texto_completo.split('\n')
                    for i, linea in enumerate(lineas):
                        if 'Fallecimiento' in linea or 'PRIMA ANUAL' in linea:
                            # Buscar números en esta línea o en la siguiente
                            numeros = re.findall(r'(\d{1,3}(?:,\d{3})*\.\d{2})', linea + (lineas[i+1] if i+1 < len(lineas) else ''))
                            if numeros and len(numeros) > 0:
                                # Tomar el valor más grande, que probablemente sea la suma asegurada
                                valores = [float(normalizar_numero(n)) for n in numeros]
                                max_valor = max(valores)
                                resultado["Suma asegurada"] = f"{max_valor:.2f}"
                                logging.info(f"Suma asegurada encontrada (línea fallecimiento): {resultado['Suma asegurada']}")
                                break

        # Para el nombre del plan, combinar con información adicional
        if resultado["Tipo de plan"] != "0":
            resultado["Nombre del plan"] = f"Aliados+ PPR {resultado['Tipo de plan']}"
            logging.info(f"Nombre del plan establecido: {resultado['Nombre del plan']}")
            
        # Si no se encontró el código postal en la dirección, buscarlo en todo el texto
        if resultado["Código Postal"] == "0":
            cp_matches = re.findall(r'[^\d](\d{5})[^\d]', texto_completo)
            for cp in cp_matches:
                # Verificar que sea un código postal mexicano válido
                if len(cp) == 5 and cp.isdigit():
                    resultado["Código Postal"] = cp
                    logging.info(f"Código postal encontrado: {cp}")
                    break

        # Para el domicilio del asegurado, usar el mismo que el contratante si no se ha encontrado
        if resultado["Domicilio del asegurado"] == "0" and resultado["Domicilio del contratante"] != "0":
            resultado["Domicilio del asegurado"] = resultado["Domicilio del contratante"]
            logging.info(f"Usando el mismo domicilio para asegurado y contratante: {resultado['Domicilio del contratante']}")

        # Buscar frecuencia de pago
        if resultado["Forma de pago"] != "0":
            if resultado["Forma de pago"] in ["ANUAL", "AGENTE"]:
                resultado["Frecuencia de pago"] = "ANUAL"
            elif "MENS" in resultado["Forma de pago"].upper():
                resultado["Frecuencia de pago"] = "MENSUAL"
            logging.info(f"Frecuencia de pago establecida: {resultado['Frecuencia de pago']}")

        # Extraer cobertura básica de la sección de coberturas
        if "Fallecimiento" in texto_completo:
            resultado["Cobertura Básica"] = "Fallecimiento"
            logging.info(f"Cobertura básica establecida: {resultado['Cobertura Básica']}")

        # Intentar calcular la prima mensual si no la encontramos directamente pero tenemos la prima anual
        if resultado["Prima mensual"] == "0" and resultado["Prima anual total"] != "0":
            try:
                # Verificar si hay una frecuencia de pago mensual
                if resultado["Frecuencia de pago"] == "MENSUAL":
                    # Dividir la prima anual entre 12 para obtener la mensual aproximada
                    prima_anual = float(resultado["Prima anual total"])
                    prima_mensual = prima_anual / 12
                    resultado["Prima mensual"] = f"{prima_mensual:.2f}"
                    logging.info(f"Prima mensual calculada: {resultado['Prima mensual']}")
            except Exception as e:
                logging.error(f"Error al calcular prima mensual: {str(e)}")

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

        # Aplicar patrones alternativos para campos críticos si no se encontraron con los principales
        for campo, patrones_alt in patrones_alternativos.items():
            if resultado[campo] == "0":
                for patron_alt in patrones_alt:
                    match = re.search(patron_alt, texto_completo, re.IGNORECASE)
                    if match:
                        resultado[campo] = match.group(1).strip()
                        logging.info(f"{campo} encontrado (patrón alternativo): {resultado[campo]}")
                        break

    except Exception as e:
        logging.error(f"Error procesando PDF de Aliados+ PPR: {str(e)}", exc_info=True)

    return resultado

def generar_markdown(datos: Dict, ruta_salida: str = "aliados_ppr.md") -> None:
    """
    Genera un archivo markdown con los datos extraídos estructurados para pólizas Aliados+ PPR.
    """
    try:
        # Limpiar los nombres antes de generar el markdown
        if datos["Nombre del contratante"] != "0":
            datos["Nombre del contratante"] = re.sub(r'\s+TIPO DE PLAN.*$', '', datos["Nombre del contratante"])
        
        if datos["Nombre del asegurado titular"] != "0":
            datos["Nombre del asegurado titular"] = re.sub(r'\s+TIPO DE PLAN.*$', '', datos["Nombre del asegurado titular"])
        
        if datos["Nombre del agente"] != "0":
            datos["Nombre del agente"] = re.sub(r'\s+(?:Fraccionado|Prima|Centro).*$', '', datos["Nombre del agente"])
        
        # Organizar datos por categorías
        info_general = {
            "Tipo de Documento": "Póliza Aliados+ PPR",
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
        md_content = "# Datos Extraídos de Póliza Aliados+ PPR\n\n"
        
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
        md_content += "El documento es una póliza Aliados+ PPR. Los valores \"Por determinar\" indican campos que no pudieron ser claramente identificados en el documento original PDF."
        
        # Guardar el archivo markdown
        with open(ruta_salida, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logging.info(f"Archivo markdown generado en {ruta_salida}")
        
    except Exception as e:
        logging.error(f"Error generando archivo markdown: {str(e)}", exc_info=True)

def extraer_datos_desde_markdown(ruta_md: str) -> Dict:
    """
    Extrae datos desde un archivo markdown estructurado para Aliados+ PPR
    """
    logging.info(f"Extrayendo datos desde archivo markdown: {ruta_md}")
    
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
        "Prima Mensual": "Prima mensual",
        "Cobertura Básica": "Cobertura Básica",
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
                        # Limitar domicilios a 50 caracteres
                        if json_key in ["Domicilio del contratante", "Domicilio del asegurado"] and len(valor) > 50:
                            resultado[json_key] = valor[:50]
                            logging.info(f"Limitado {json_key} a 50 caracteres: {resultado[json_key]}")
                        logging.info(f"Extraído desde markdown: {json_key} = {resultado[json_key]}")
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
    if resultado["Domicilio del contratante"] != "0" and resultado["Domicilio del asegurado"] == "0":
        logging.info(f"Usando el mismo domicilio para asegurado y contratante: {resultado['Domicilio del contratante']}")
        resultado["Domicilio del asegurado"] = resultado["Domicilio del contratante"]
        # Asegurar que ambos estén limitados a 50 caracteres
        if len(resultado["Domicilio del contratante"]) > 50:
            resultado["Domicilio del contratante"] = resultado["Domicilio del contratante"][:50]
            resultado["Domicilio del asegurado"] = resultado["Domicilio del asegurado"][:50]
            logging.info(f"Limitada dirección a 50 caracteres después de copiarla")

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
    ruta_md = f"{nombre_base}_aliados_ppr.md"
    
    # Verificar si existe el archivo markdown, si no existe, crear uno
    if not os.path.exists(ruta_md):
        # Extraer datos del PDF
        datos = extraer_datos_poliza_aliados_ppr(ruta_pdf)
        # Generar archivo markdown con los datos extraídos
        generar_markdown(datos, ruta_md)
        logging.info(f"Archivo markdown creado: {ruta_md}")
    else:
        logging.info(f"Usando archivo markdown existente: {ruta_md}")
    
    # Extraer datos desde el markdown (puede incluir información manual)
    datos_finales = extraer_datos_desde_markdown(ruta_md)
    
    # Guardar los datos extraídos del markdown en JSON
    guardar_a_json(datos_finales, ruta_json)
    
    # Eliminar el archivo markdown después de completar el proceso
    try:
        os.remove(ruta_md)
        logging.info(f"Archivo markdown eliminado: {ruta_md}")
    except Exception as e:
        logging.error(f"Error al eliminar archivo markdown {ruta_md}: {str(e)}")
    
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
    
    # Eliminar cualquier archivo markdown restante en el directorio actual
    archivos_md = glob.glob("*_aliados_ppr.md")
    for archivo_md in archivos_md:
        try:
            os.remove(archivo_md)
            logging.info(f"Archivo markdown adicional eliminado: {archivo_md}")
        except Exception as e:
            logging.error(f"Error al eliminar archivo markdown adicional {archivo_md}: {str(e)}")

def main():
    """
    Función principal para ejecutar el script desde línea de comandos
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Extractor de datos de pólizas Aliados+ PPR desde PDFs")
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
