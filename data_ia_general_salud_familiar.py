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
    Detecta si el documento es una póliza de Gastos Médicos Mayores Familiar.
    """
    # Patrones para identificar documentos de Gastos Médicos Familiares
    if re.search(r'Gastos M[ée]dicos Mayores Individual|Gastos M[ée]dicos Mayores.*Familiar|Car[áa]tula de p[óo]liza.*Gastos M[ée]dicos', texto_pdf, re.IGNORECASE):
        logging.info("Detectado: Documento de Gastos Médicos Mayores Familiar")
        return "GASTOS_MEDICOS_FAMILIAR"
    
    # Si no coincide con ningún patrón conocido
    logging.warning("Tipo de documento no identificado como Gastos Médicos Mayores Familiar")
    return "DESCONOCIDO"

def extraer_datos_poliza_salud_familiar(pdf_path: str) -> Dict:
    """
    Extrae datos de una póliza de Gastos Médicos Mayores Familiar desde un archivo PDF.
    """
    logging.info(f"Procesando archivo Gastos Médicos Mayores Familiar: {pdf_path}")
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
        "Suma Asegurada": "0",
        "Deducible": "0",
        "Coaseguro": "0",
        "Tope de Coaseguro": "0",
        "Gama Hospitalaria": "0",
        "Tipo de Red": "0",
        "Tabulador Médico": "0",
        "Periodo de pago de siniestro": "0",
        "Recargo por pago fraccionado": "0",
        "Derecho de póliza": "0",
        "Zona Tarificación": "0",
        "Descuento familiar": "0",
        "Cesión de Comisión": "0"
    }

    # Inicializar lista para coberturas incluidas y adicionales
    coberturas_incluidas = []
    coberturas_adicionales = []
    servicios_costo = []

    try:
        # Extraer texto del PDF usando PyMuPDF para mejor manejo de layout
        doc = fitz.open(pdf_path)
        texto_completo = ""
        for page in doc:
            texto_completo += page.get_text("text", sort=True) + "\n"  # Usar sort=True para orden de lectura
        doc.close()

        # Detectar tipo de documento
        tipo_documento = detectar_tipo_documento(texto_completo)
        if tipo_documento != "GASTOS_MEDICOS_FAMILIAR":
            logging.warning(f"Este documento no parece ser una póliza de Gastos Médicos Mayores Familiar: {tipo_documento}")

        # Patrones específicos para el formato Gastos Médicos Mayores Familiar
        patrones = {
            "Nombre del contratante": r'Nombre\s*:\s*([A-ZÁ-Ú\s,.]+?)(?=\s+Domicilio|$)',
            "Domicilio del contratante": r'Domicilio\s*:\s*(.*?)(?=\s+LOS CABOS|$)',
            "Ciudad del contratante": r'Ciudad:\s+([A-ZÁ-Ú\s,.]+)',
            "Código Postal": r'C\.P\.\s+(\d{5})',
            "Nombre del asegurado titular": r'Datos del Asegurado Titular\s+Nombre\s*:\s*([A-ZÁ-Ú\s,.]+?)(?=\s+Domicilio|$)',
            "Domicilio del asegurado": r'Datos del Asegurado Titular.*?Domicilio\s*:\s*(.*?)(?=\s+LOS CABOS|$)',
            "Ciudad del asegurado": r'Datos del Asegurado Titular.*?Ciudad:\s+([A-ZÁ-Ú\s,.]+)',
            "R.F.C.": r'R\.F\.C\.\s*:\s*([A-Z0-9]{10,13})',
            "Teléfono": r'Teléfono:\s+([0-9]{7,10})',
            "Número de póliza": r'P[óo]liza\s+([0-9A-Z]+)',
            "Solicitud": r'Solicitud\s+(\d{5,14})',
            "Tipo de Plan": r'Tipo de [Pp]lan\s+([A-Za-zÁ-Úá-ú\s]+)',
            "Fecha de inicio de vigencia": r'Fecha de inicio de vigencia\s+(\d{2}/\d{2}/\d{4})',
            "Fecha de fin de vigencia": r'Fecha de fin de vigencia\s+(\d{2}/\d{2}/\d{4})',
            "Fecha de emisión": r'Fecha de emisión\s+(\d{2}/\d{2}/\d{4})',
            "Frecuencia de pago": r'Frecuencia de pago\s+([A-ZÁ-Ú\s]+)',
            "Tipo de pago": r'Tipo de pago\s+([A-ZÁ-Ú\s]+)',
            "Zona Tarificación": r'Zona Tarificación:\s+Zona\s+(\d+)',
            "Periodo de pago de siniestro": r'Periodo de pago de siniestro\s+(\d+\s+años)',
            "Suma Asegurada": r'SumaAsegurada\s+\$\s+([\d,]+\s+[M]\.[N]\.)',
            "Deducible": r'Deducible\s+\$\s+([\d,]+\s+[M]\.[N]\.)',
            "Coaseguro": r'Coaseguro\s+(\d+\s*%)',
            "Tope de Coaseguro": r'Tope de Coaseguro\s+\$\s+([\d,]+\s+[M]\.[N]\.)',
            "Gama Hospitalaria": r'Gama Hospitalaria\s+([A-ZÁ-Ú\s]+)',
            "Tipo de Red": r'Tipo de Red\s+([A-ZÁ-Ú\s]+)',
            "Tabulador Médico": r'Tabulador Médico\s+([A-ZÁ-Ú\s]+)',
            "Prima Neta": r'Prima Neta\s+([\d,]+\.\d{2})',
            "Recargo por pago fraccionado": r'Recargo por pago fraccionado\s+([\d,]+\.\d{2}|[\d,]+|0)',
            "Derecho de póliza": r'Derecho de póliza\s+([\d,]+\.\d{2})',
            "I.V.A.": r'I\.V\.A\.\s+([\d,]+\.\d{2})',
            "Prima anual total": r'Prima anual total\s+([\d,]+\.\d{2})',
            "Descuento familiar": r'Descuento familiar\s+([\d,]+\.\d{2}|[\d,]+|0)',
            "Cesión de Comisión": r'Cesión de Comisión\s+([\d,]+\.\d{2}|[\d,]+|0)',
            "Clave Agente": r'Agente:?\s+(\d+|Número\s+\d{8})',
            "Nombre del agente": r'Agente\s+\d+\s+([A-ZÁ-Ú\s,.]+)',
            "Promotor": r'Promotor\s*:\s*(\d+)'
        }

        # Patrones para el formato tabular (como en la imagen proporcionada)
        patrones_tabulares = {
            "Número de póliza": r'Póliza\s*\n\s*([0-9A-Z]+)',
            "Tipo de Plan": r'Tipo de plan\s*\n\s*([A-Za-zÁ-Úá-ú\s]+)',
            "Solicitud": r'Solicitud\s*\n\s*(\d{5,14})',
            "Fecha de inicio de vigencia": r'Fecha de inicio de vigencia\s*\n\s*(\d{2}/\d{2}/\d{4})',
            "Fecha de fin de vigencia": r'Fecha de fin de vigencia\s*\n\s*(\d{2}/\d{2}/\d{4})',
            "Fecha de emisión": r'Fecha de emisión\s*\n\s*(\d{2}/\d{2}/\d{4})',
            "Frecuencia de pago": r'Frecuencia de pago\s*\n\s*([A-Za-zÁ-Úá-ú\s]+)',
            "Tipo de pago": r'Tipo de pago\s*\n\s*([A-Za-zÁ-Úá-ú\s]+)',
            "Prima Neta": r'Prima Neta\s*\n\s*([\d,]+\.\d{2})',
            "Descuento familiar": r'Descuento familiar\s*\n\s*([0-9]+)',
            "Cesión de Comisión": r'Cesión de Comisión\s*\n\s*([0-9]+)',
            "Recargo por pago fraccionado": r'Recargo por pago fraccionado\s*\n\s*([0-9]+)',
            "Derecho de póliza": r'Derecho de póliza\s*\n\s*([\d,]+\.\d{2})',
            "I.V.A.": r'I\.V\.A\.\s*\n\s*([\d,]+\.\d{2})',
            "Prima anual total": r'Prima anual total\s*\n\s*([\d,]+\.\d{2})'
        }

        # Extraer valores usando patrones específicos y patrones tabulares
        for campo, patron in list(patrones.items()) + list(patrones_tabulares.items()):
            match = re.search(patron, texto_completo, re.MULTILINE | re.IGNORECASE)
            if match:
                if campo in ["Domicilio del contratante", "Domicilio del asegurado"]:
                    valor = match.group(1).strip() if match.group(1) else match.group(0).strip()
                    # Limpiar saltos de línea y espacios múltiples
                    valor = re.sub(r'\s*\n\s*', ' ', valor)
                    resultado[campo] = valor
                    logging.info(f"{campo} extraído: {valor}")
                elif campo in ["Prima Neta", "Prima anual total", "I.V.A.", "Recargo por pago fraccionado", "Derecho de póliza", "Descuento familiar", "Cesión de Comisión"]:
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

        # Búsqueda más específica para la tabla de datos financieros
        financieros_pattern = r'Prima\s*\n\s*Descuento familiar\s*\n\s*(\d+)\s*\n\s*Cesión de Comisión\s*\n\s*(\d+)\s*\n\s*Prima Neta\s*\n\s*([\d,]+\.\d{2})\s*\n\s*Recargo por pago fraccionado\s*\n\s*(\d+)\s*\n\s*Derecho de póliza\s*\n\s*([\d,]+\.\d{2})\s*\n\s*I\.V\.A\.\s*\n\s*([\d,]+\.\d{2})\s*\n\s*Prima anual total\s*\n\s*([\d,]+\.\d{2})'
        
        match_financieros = re.search(financieros_pattern, texto_completo, re.MULTILINE)
        if match_financieros:
            resultado["Descuento familiar"] = normalizar_numero(match_financieros.group(1))
            resultado["Cesión de Comisión"] = normalizar_numero(match_financieros.group(2))
            resultado["Prima Neta"] = normalizar_numero(match_financieros.group(3))
            resultado["Recargo por pago fraccionado"] = normalizar_numero(match_financieros.group(4))
            resultado["Derecho de póliza"] = normalizar_numero(match_financieros.group(5))
            resultado["I.V.A."] = normalizar_numero(match_financieros.group(6))
            resultado["Prima anual total"] = normalizar_numero(match_financieros.group(7))
            logging.info(f"Datos financieros extraídos del patrón completo de tabla")
        
        # Buscar en formato de tabla compacta
        poliza_pattern = r'Póliza\s*\n\s*([0-9A-Z]+)\s*\n\s*Tipo de plan\s*\n\s*([A-Za-z\s]+)\s*\n\s*Solicitud\s*\n\s*(\d+)\s*\n\s*Fecha de inicio de vigencia\s*\n\s*(\d{2}/\d{2}/\d{4})\s*\n\s*Fecha de fin de vigencia\s*\n\s*(\d{2}/\d{2}/\d{4})\s*\n\s*Fecha de emisión\s*\n\s*(\d{2}/\d{2}/\d{4})\s*\n\s*Frecuencia de pago\s*\n\s*([A-Za-zÁ-Úá-ú\s]+)\s*\n\s*Tipo de pago\s*\n\s*([A-Za-zÁ-Úá-ú\s]+)'
        
        match_poliza = re.search(poliza_pattern, texto_completo, re.MULTILINE)
        if match_poliza:
            resultado["Número de póliza"] = match_poliza.group(1)
            resultado["Tipo de Plan"] = match_poliza.group(2)
            resultado["Solicitud"] = match_poliza.group(3)
            resultado["Fecha de inicio de vigencia"] = match_poliza.group(4)
            resultado["Fecha de fin de vigencia"] = match_poliza.group(5)
            resultado["Fecha de emisión"] = match_poliza.group(6)
            resultado["Frecuencia de pago"] = match_poliza.group(7)
            resultado["Tipo de pago"] = match_poliza.group(8)
            logging.info(f"Datos de póliza extraídos del patrón completo de tabla")

        # Extraer coberturas incluidas
        cobertura_pattern = r'Incluidos en Básica\s+(.*?)(?=Coberturas adicionales con costo|$)'
        cobertura_match = re.search(cobertura_pattern, texto_completo, re.DOTALL | re.IGNORECASE)
        if cobertura_match:
            cobertura_text = cobertura_match.group(1).strip()
            # Extraer líneas de coberturas
            for linea in cobertura_text.split('\n'):
                if linea.strip() and not linea.strip().startswith('Cobertura') and not linea.strip().startswith('Suma') and not linea.strip().startswith('Deducible'):
                    # Extraer nombre de la cobertura
                    cobertura_nombre_match = re.match(r'^([A-Za-zÁ-Úá-ú\s]+)', linea.strip())
                    if cobertura_nombre_match:
                        nombre_cobertura = cobertura_nombre_match.group(1).strip()
                        # Buscar los valores asociados (suma asegurada, deducible, coaseguro)
                        suma_asegurada = "N/A"
                        deducible = "N/A"
                        coaseguro = "N/A"
                        
                        # Intentar extraer valores
                        suma_match = re.search(r'(\d+[\.,]?\d*)', linea)
                        if suma_match:
                            suma_asegurada = suma_match.group(1)
                        
                        # Extraer deducible y coaseguro (pueden estar en la misma línea o en texto general)
                        deducible_match = re.search(r'Deducible[:\s]+([A-Za-zÁ-Úá-ú0-9\s/\.]+)', linea)
                        if deducible_match:
                            deducible = deducible_match.group(1).strip()
                        
                        coaseguro_match = re.search(r'Coaseguro[:\s]+([A-Za-zÁ-Úá-ú0-9\s%\.]+)', linea)
                        if coaseguro_match:
                            coaseguro = coaseguro_match.group(1).strip()
                        
                        coberturas_incluidas.append({
                            "Nombre": nombre_cobertura,
                            "Suma Asegurada": suma_asegurada,
                            "Deducible": deducible,
                            "Coaseguro": coaseguro
                        })

        # Extraer coberturas adicionales con costo
        cobertura_adicional_pattern = r'Coberturas adicionales con costo\s+(.*?)(?=Servicios\s+con costo|$)'
        cobertura_adicional_match = re.search(cobertura_adicional_pattern, texto_completo, re.DOTALL | re.IGNORECASE)
        if cobertura_adicional_match:
            cobertura_text = cobertura_adicional_match.group(1).strip()
            # Extraer líneas de coberturas
            lineas = [l.strip() for l in cobertura_text.split('\n') if l.strip()]
            i = 0
            while i < len(lineas):
                linea = lineas[i]
                if not linea.startswith('Coberturas') and not linea.startswith('Suma') and not linea.startswith('Deducible'):
                    cobertura_nombre_match = re.match(r'^([A-Za-zÁ-Úá-ú\s]+)', linea)
                    if cobertura_nombre_match:
                        nombre_cobertura = cobertura_nombre_match.group(1).strip()
                        suma_asegurada = "N/A"
                        deducible = "N/A"
                        coaseguro = "N/A"
                        
                        # Buscar suma asegurada
                        suma_match = re.search(r'(Max \$[\d,]+ USD|Básica|De acuerdo a Condiciones Generales)', cobertura_text)
                        if suma_match:
                            suma_asegurada = suma_match.group(1)
                        
                        # Buscar deducible y coaseguro
                        deducible_match = re.search(r'(\$\d+[\.,]?\d*\s+[M]\.[N]\.|No Aplica|\$\d+ USD)', cobertura_text)
                        if deducible_match:
                            deducible = deducible_match.group(1)
                        
                        coaseguro_match = re.search(r'(\d+\s*%|No Aplica)', cobertura_text)
                        if coaseguro_match:
                            coaseguro = coaseguro_match.group(1)
                        
                        coberturas_adicionales.append({
                            "Nombre": nombre_cobertura,
                            "Suma Asegurada": suma_asegurada,
                            "Deducible": deducible,
                            "Coaseguro": coaseguro
                        })
                i += 1

        # Extraer servicios con costo
        servicios_pattern = r'Servicios\s+con costo\s+(.*?)(?=Prima|$)'
        servicios_match = re.search(servicios_pattern, texto_completo, re.DOTALL | re.IGNORECASE)
        if servicios_match:
            servicios_text = servicios_match.group(1).strip()
            # Extraer líneas de servicios
            lineas = [l.strip() for l in servicios_text.split('\n') if l.strip()]
            i = 0
            while i < len(lineas):
                linea = lineas[i]
                if not linea.startswith('Servicio') and not linea.startswith('Costo'):
                    servicio_match = re.match(r'^([A-Za-zÁ-Úá-ú\s]+)', linea)
                    if servicio_match:
                        nombre_servicio = servicio_match.group(1).strip()
                        costo = "No Aplica"
                        
                        # Buscar costo asociado
                        costo_match = re.search(r'(No Aplica)', linea)
                        if costo_match:
                            costo = costo_match.group(1)
                        
                        servicios_costo.append({
                            "Nombre": nombre_servicio,
                            "Costo": costo
                        })
                i += 1

        # Añadir las coberturas y servicios al resultado
        resultado["Coberturas Incluidas"] = coberturas_incluidas
        resultado["Coberturas Adicionales"] = coberturas_adicionales
        resultado["Servicios con Costo"] = servicios_costo

        # Post-procesamiento específico para este formato

        # Tratar de extraer el código postal del domicilio si no lo encontramos directamente
        if resultado["Código Postal"] == "0" and resultado["Domicilio del contratante"] != "0":
            cp_match = re.search(r'C\.P\.\s*(\d{5})', resultado["Domicilio del contratante"], re.IGNORECASE)
            if cp_match:
                resultado["Código Postal"] = cp_match.group(1)
                logging.info(f"Código postal extraído del domicilio: {resultado['Código Postal']}")
            else:
                # Intenta buscar solo 5 dígitos seguidos
                cp_match = re.search(r'(\d{5})', resultado["Domicilio del contratante"])
                if cp_match:
                    resultado["Código Postal"] = cp_match.group(1).strip()
                    logging.info(f"Código postal extraído del domicilio (regex alternativo): {resultado['Código Postal']}")

        # Corregir valor de Coaseguro eliminando espacios y asegurando formato
        if resultado["Coaseguro"] != "0":
            resultado["Coaseguro"] = resultado["Coaseguro"].replace(" ", "")
            if not resultado["Coaseguro"].endswith("%"):
                resultado["Coaseguro"] += "%"
                
        # Intento específico para extraer el número de póliza y tipo de plan correctamente
        poliza_match = re.search(r'Póliza\s*\n\s*([A-Z0-9]+)', texto_completo)
        if poliza_match:
            resultado["Número de póliza"] = poliza_match.group(1).strip()
            logging.info(f"Número de póliza extraído (alt): {resultado['Número de póliza']}")
        
        # Buscar en el texto cualquier patrón con dígitos seguidos de posible código de póliza
        if resultado["Número de póliza"] == "0" or len(resultado["Número de póliza"]) < 4 or resultado["Número de póliza"] == "N":
            # Patrones específicos para buscar números de póliza
            poliza_patterns = [
                r'[0-9]{5,}[A-Z][0-9]{2}',  # Formato común de pólizas con un patrón como "90687X02"
                r'[0-9]{6,}H',  # Formato como "1059823H"
                r'GP[0-9]{7}',  # Formato como "GP17847008"
                r'[0-9]{3,}-[0-9]{3,}-[0-9]{3,}'  # Formato como "123-456-789"
            ]
            
            # Intentar varios patrones
            for pattern in poliza_patterns:
                poliza_alt_match = re.search(pattern, texto_completo)
                if poliza_alt_match:
                    resultado["Número de póliza"] = poliza_alt_match.group(0).strip()
                    logging.info(f"Número de póliza extraído (pattern): {resultado['Número de póliza']}")
                    break
            
            # Si todavía no encontramos, buscar directamente en líneas que contengan "Póliza"
            if resultado["Número de póliza"] == "0" or len(resultado["Número de póliza"]) < 4 or resultado["Número de póliza"] == "N":
                for line in texto_completo.split('\n'):
                    if "Póliza" in line:
                        digits_match = re.search(r'([0-9]{5,}[A-Z0-9]*)', line)
                        if digits_match:
                            resultado["Número de póliza"] = digits_match.group(1).strip()
                            logging.info(f"Número de póliza extraído (línea): {resultado['Número de póliza']}")
                            break
        
        tipo_plan_match = re.search(r'Tipo de plan\s*\n\s*([A-Za-zÁ-Úá-ú\s]+)', texto_completo)
        if tipo_plan_match:
            resultado["Tipo de Plan"] = tipo_plan_match.group(1).strip()
            logging.info(f"Tipo de Plan extraído (alt): {resultado['Tipo de Plan']}")
        
        # Si no encontramos el asegurado titular, podría ser el mismo que el contratante
        if resultado["Nombre del asegurado titular"] == "0" and resultado["Nombre del contratante"] != "0":
            resultado["Nombre del asegurado titular"] = resultado["Nombre del contratante"]
            logging.info(f"Nombre del asegurado titular asumido como el contratante: {resultado['Nombre del asegurado titular']}")
        
        # Buscar la clave de agente y nombre en formato específico
        agente_match = re.search(r'Agente:\s*Número\s*\n(\d+)\s+([A-ZÁ-Ú\s,.]+)', texto_completo, re.MULTILINE)
        if agente_match:
            resultado["Clave Agente"] = agente_match.group(1).strip()
            resultado["Nombre del agente"] = agente_match.group(2).strip()
            logging.info(f"Clave Agente extraído (alt): {resultado['Clave Agente']}")
            logging.info(f"Nombre del agente extraído (alt): {resultado['Nombre del agente']}")
        
        # Extraer la solicitud con otro patrón
        solicitud_match = re.search(r'Solicitud\s*\n\s*(\d+)', texto_completo)
        if solicitud_match:
            resultado["Solicitud"] = solicitud_match.group(1).strip()
            logging.info(f"Solicitud extraída (alt): {resultado['Solicitud']}")

        # Buscar fechas en formato DD/MM/YYYY
        fecha_emision_match = re.search(r'Fecha\s+de\s+Emisi[óo]n\s*[^\d]*(\d{2}/\d{2}/\d{4})', texto_completo, re.IGNORECASE)
        fecha_inicio_match = re.search(r'(?:Vigencia\s+desde|Fecha\s+de\s+inicio\s+de\s+vigencia)\s*[^\d]*(\d{2}/\d{2}/\d{4})', texto_completo, re.IGNORECASE)
        fecha_fin_match = re.search(r'(?:Vigencia\s+hasta|Fecha\s+de\s+fin\s+de\s+vigencia)\s*[^\d]*(\d{2}/\d{2}/\d{4})', texto_completo, re.IGNORECASE)
        
        # Buscar fechas en formato DD/MMM/YYYY
        fecha_emision_alt_match = re.search(r'Fecha\s+de\s+Emisi[óo]n\s*[^\d]*(\d{2}/[A-Za-z]{3}/\d{4})', texto_completo, re.IGNORECASE)
        
        # Buscar formato de vigencia con "A" como separador
        fecha_vigencia_alt_match = re.search(r'Vigencia\s*[^\d]*(\d{2}/[A-Za-z]{3}/\d{4})\s*A\s*(\d{2}/[A-Za-z]{3}/\d{4})', texto_completo, re.IGNORECASE)
        
        # Asignar fechas extraídas
        if fecha_emision_match:
            resultado['Fecha de emisión'] = fecha_emision_match.group(1)
            logging.info(f"Fecha de emisión extraída: {resultado['Fecha de emisión']}")
        elif fecha_emision_alt_match:
            resultado['Fecha de emisión'] = fecha_emision_alt_match.group(1)
            logging.info(f"Fecha de emisión extraída (formato alt): {resultado['Fecha de emisión']}")
        
        if fecha_inicio_match:
            resultado['Fecha de inicio de vigencia'] = fecha_inicio_match.group(1)
            logging.info(f"Fecha de inicio de vigencia extraída: {resultado['Fecha de inicio de vigencia']}")
        elif fecha_vigencia_alt_match:
            resultado['Fecha de inicio de vigencia'] = fecha_vigencia_alt_match.group(1)
            logging.info(f"Fecha de inicio de vigencia extraída (formato alt): {resultado['Fecha de inicio de vigencia']}")
            
        if fecha_fin_match:
            resultado['Fecha de fin de vigencia'] = fecha_fin_match.group(1)
            logging.info(f"Fecha de fin de vigencia extraída: {resultado['Fecha de fin de vigencia']}")
        elif fecha_vigencia_alt_match:
            resultado['Fecha de fin de vigencia'] = fecha_vigencia_alt_match.group(2)
            logging.info(f"Fecha de fin de vigencia extraída (formato alt): {resultado['Fecha de fin de vigencia']}")

    except Exception as e:
        logging.error(f"Error procesando PDF de Gastos Médicos Mayores Familiar: {str(e)}", exc_info=True)

    return resultado

def generar_markdown(datos: Dict, ruta_salida: str = "salud_familiar.md") -> None:
    """
    Genera un archivo markdown con los datos extraídos estructurados para pólizas de Gastos Médicos Mayores Familiar.
    """
    try:
        # Organizar datos por categorías
        info_general = {
            "Tipo de Documento": "Póliza de Gastos Médicos Mayores Familiar",
            "Número de Póliza": datos["Número de póliza"] if datos["Número de póliza"] != "0" else "Por determinar",
            "Tipo de Plan": datos["Tipo de Plan"] if datos["Tipo de Plan"] != "0" else "Por determinar",
            "Solicitud": datos["Solicitud"] if datos["Solicitud"] != "0" else "Por determinar"
        }
        
        datos_contratante = {
            "Nombre del Contratante": datos["Nombre del contratante"] if datos["Nombre del contratante"] != "0" else "Por determinar",
            "R.F.C.": datos["R.F.C."] if datos["R.F.C."] != "0" else "Por determinar",
            "Domicilio del Contratante": datos["Domicilio del contratante"] if datos["Domicilio del contratante"] != "0" else "Por determinar",
            "Ciudad": datos["Ciudad del contratante"] if datos["Ciudad del contratante"] != "0" else "Por determinar",
            "Código Postal": datos["Código Postal"] if datos["Código Postal"] != "0" else "Por determinar",
            "Teléfono": datos["Teléfono"] if datos["Teléfono"] != "0" else "Por determinar"
        }
        
        datos_asegurado = {
            "Nombre del Asegurado Titular": datos["Nombre del asegurado titular"] if datos["Nombre del asegurado titular"] != "0" else "Por determinar",
            "Domicilio del Asegurado": datos["Domicilio del asegurado"] if datos["Domicilio del asegurado"] != "0" else "Por determinar",
            "Ciudad": datos["Ciudad del asegurado"] if datos["Ciudad del asegurado"] != "0" else "Por determinar",
            "Zona de Tarificación": datos["Zona Tarificación"] if datos["Zona Tarificación"] != "0" else "Por determinar"
        }
        
        datos_agente = {
            "Clave Agente": datos["Clave Agente"] if datos["Clave Agente"] != "0" else "Por determinar",
            "Nombre del Agente": datos["Nombre del agente"] if datos["Nombre del agente"] != "0" else "Por determinar",
            "Promotor": datos["Promotor"] if datos["Promotor"] != "0" else "Por determinar"
        }
        
        fechas = {
            "Fecha de Emisión": datos["Fecha de emisión"] if datos["Fecha de emisión"] != "0" else "Por determinar",
            "Fecha de Inicio de Vigencia": datos["Fecha de inicio de vigencia"] if datos["Fecha de inicio de vigencia"] != "0" else "Por determinar",
            "Fecha de Fin de Vigencia": datos["Fecha de fin de vigencia"] if datos["Fecha de fin de vigencia"] != "0" else "Por determinar"
        }
        
        condiciones = {
            "Periodo de Pago de Siniestro": datos["Periodo de pago de siniestro"] if datos["Periodo de pago de siniestro"] != "0" else "Por determinar",
            "Suma Asegurada": datos["Suma Asegurada"] if datos["Suma Asegurada"] != "0" else "Por determinar",
            "Deducible": datos["Deducible"] if datos["Deducible"] != "0" else "Por determinar",
            "Coaseguro": datos["Coaseguro"] if datos["Coaseguro"] != "0" else "Por determinar",
            "Tope de Coaseguro": datos["Tope de Coaseguro"] if datos["Tope de Coaseguro"] != "0" else "Por determinar",
            "Tabulador Médico": datos["Tabulador Médico"] if datos["Tabulador Médico"] != "0" else "Por determinar",
            "Gama Hospitalaria": datos["Gama Hospitalaria"] if datos["Gama Hospitalaria"] != "0" else "Por determinar",
            "Tipo de Red": datos["Tipo de Red"] if datos["Tipo de Red"] != "0" else "Por determinar"
        }
        
        info_financiera = {
            "Prima Neta": datos["Prima Neta"] if datos["Prima Neta"] != "0" else "Por determinar",
            "Recargo por pago fraccionado": datos["Recargo por pago fraccionado"] if datos["Recargo por pago fraccionado"] != "0" else "Por determinar",
            "Derecho de póliza": datos["Derecho de póliza"] if datos["Derecho de póliza"] != "0" else "Por determinar",
            "I.V.A.": datos["I.V.A."] if datos["I.V.A."] != "0" else "Por determinar",
            "Prima anual total": datos["Prima anual total"] if datos["Prima anual total"] != "0" else "Por determinar",
            "Descuento familiar": datos["Descuento familiar"] if datos["Descuento familiar"] != "0" else "Por determinar",
            "Cesión de Comisión": datos["Cesión de Comisión"] if datos["Cesión de Comisión"] != "0" else "Por determinar",
            "Frecuencia de pago": datos["Frecuencia de pago"] if datos["Frecuencia de pago"] != "0" else "Por determinar",
            "Tipo de pago": datos["Tipo de pago"] if datos["Tipo de pago"] != "0" else "Por determinar"
        }
        
        # Construir el markdown
        md_content = "# Datos Extraídos de Póliza de Gastos Médicos Mayores Familiar\n\n"
        
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
        md_content += "## Datos del Asegurado Titular\n"
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
        
        # Condiciones Contratadas
        md_content += "## Condiciones Contratadas\n"
        for clave, valor in condiciones.items():
            md_content += f"- **{clave}**: {valor}\n"
        md_content += "\n"
        
        # Información Financiera
        md_content += "## Información Financiera\n"
        for clave, valor in info_financiera.items():
            md_content += f"- **{clave}**: {valor}\n"
        md_content += "\n"
        
        # Coberturas Incluidas
        md_content += "## Coberturas Incluidas en Básica\n"
        if datos["Coberturas Incluidas"]:
            for cobertura in datos["Coberturas Incluidas"]:
                md_content += f"### {cobertura['Nombre']}\n"
                md_content += f"- **Suma Asegurada**: {cobertura['Suma Asegurada']}\n"
                md_content += f"- **Deducible**: {cobertura['Deducible']}\n"
                md_content += f"- **Coaseguro**: {cobertura['Coaseguro']}\n"
                md_content += "\n"
        else:
            md_content += "No se encontraron coberturas incluidas específicas.\n\n"
        
        # Coberturas Adicionales
        md_content += "## Coberturas Adicionales con Costo\n"
        if datos["Coberturas Adicionales"]:
            for cobertura in datos["Coberturas Adicionales"]:
                md_content += f"### {cobertura['Nombre']}\n"
                md_content += f"- **Suma Asegurada**: {cobertura['Suma Asegurada']}\n"
                md_content += f"- **Deducible**: {cobertura['Deducible']}\n"
                md_content += f"- **Coaseguro**: {cobertura['Coaseguro']}\n"
                md_content += "\n"
        else:
            md_content += "No se encontraron coberturas adicionales específicas.\n\n"
        
        # Servicios con Costo
        md_content += "## Servicios con Costo\n"
        if datos["Servicios con Costo"]:
            for servicio in datos["Servicios con Costo"]:
                md_content += f"- **{servicio['Nombre']}**: {servicio['Costo']}\n"
            md_content += "\n"
        else:
            md_content += "No se encontraron servicios con costo específicos.\n\n"
        
        md_content += "Este documento es una póliza de Gastos Médicos Mayores Familiar. Los valores \"Por determinar\" indican campos que no pudieron ser claramente identificados en el documento original PDF."
        
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
    Procesa un archivo PDF de Gastos Médicos Mayores Familiar y guarda los resultados en markdown y JSON.
    
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
        datos = extraer_datos_poliza_salud_familiar(ruta_pdf)
        
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
    
    parser = argparse.ArgumentParser(description='Procesa archivos PDF de pólizas de Gastos Médicos Mayores Familiar y extrae sus datos')
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