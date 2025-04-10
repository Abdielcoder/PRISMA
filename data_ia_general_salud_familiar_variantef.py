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
    Detecta si el documento es de tipo Gastos Médicos Mayores Familiar Variante F.
    
    Args:
        texto (str): Texto extraído del PDF
        
    Returns:
        str: Tipo de documento detectado
    """
    # Patrones para identificar Gastos Médicos Mayores Familiar Variante F
    patrones_salud_familiar_variantef = [
        r"gastos médicos mayores individual/familiar",
        r"caratula de poliza",
        r"axa",
        r"prima neta",
        r"gastos de expedición",
        r"prima base i\.v\.a\.",
        r"prima total"
    ]
    
    # Contar cuántos patrones coinciden
    coincidencias = sum(1 for pattern in patrones_salud_familiar_variantef if re.search(pattern, texto, re.IGNORECASE))
    
    # Si más del 60% de los patrones coinciden, consideramos que es el documento correcto
    if coincidencias >= len(patrones_salud_familiar_variantef) * 0.6:
        return "GASTOS_MEDICOS_FAMILIAR_VARIANTEF"
    return "DESCONOCIDO"

def extraer_datos_poliza_salud_familiar_variantef(pdf_path: str) -> Dict:
    """
    Extrae datos de una póliza de Gastos Médicos Mayores Familiar Variante F desde un archivo PDF.
    """
    logging.info(f"Procesando archivo Gastos Médicos Mayores Familiar Variante F: {pdf_path}")
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
        "Moneda": "MXN",
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
        "Cesión de Comisión": "0",
        "Emergencias en el Extranjero": "0",
        "Medicamentos fuera del hospital": "0",
        "Maternidad": "0",
        "Protección Dental": "0",
        "Tu Médico 24 Hrs": "0",
        "Tipo de plan solicitado": "Individual"
    }

    # Inicializar lista para coberturas incluidas y adicionales
    coberturas_incluidas = []
    coberturas_adicionales = []
    servicios_costo = []

    try:
        # Extraer texto del PDF usando PyMuPDF para mejor manejo de layout
        doc = fitz.open(pdf_path)
        texto_completo = ""
        texto_completo_raw = ""
        for page in doc:
            texto_completo += page.get_text("text", sort=True) + "\n"  # Usar sort=True para orden de lectura
            texto_completo_raw += page.get_text() + "\n"  # Sin ordenar para capturar texto tal como está
        doc.close()

        # Detección de formato tabular estándar AXA
        # 1. Extraer número de póliza, tipo de plan y solicitud
        poliza_pattern = r'Póliza\s*\n?\s*([0-9A-Z]+)'
        solicitud_pattern = r'Solicitud\s*\n?\s*(\d+)'
        tipo_plan_pattern = r'Tipo de plan\s*\n?\s*([A-Za-z\s]+)'
        
        # Patrones de fechas
        fecha_inicio_pattern = r'Fecha de inicio de vigencia\s*\n?\s*(\d{2}/\d{2}/\d{4})'
        fecha_fin_pattern = r'Fecha de fin de vigencia\s*\n?\s*(\d{2}/\d{2}/\d{4})'
        fecha_emision_pattern = r'Fecha de emisión\s*\n?\s*(\d{2}/\d{2}/\d{4})'
        
        # Patrones de pago
        frecuencia_pago_pattern = r'Frecuencia de pago\s*\n?\s*([A-Za-z]+)'
        tipo_pago_pattern = r'Tipo de pago\s*\n?\s*([A-Za-z]+)'
        
        # Patrones del contratante y asegurado
        contratante_nombre_pattern = r'Datos del contratante\s*\n?\s*Nombre\s*:\s*([A-ZÁ-Ú\s,.]+)'
        contratante_domicilio_pattern = r'Domicilio\s*:\s*([^C]*)'
        contratante_ciudad_pattern = r'Ciudad\s*:\s*([A-ZÁ-Ú\s,.]+)'
        contratante_cp_pattern = r'C\.P\.\s*(\d{5})'
        
        asegurado_nombre_pattern = r'Datos del Asegurado Titular\s*\n?\s*Nombre\s*:\s*([A-ZÁ-Ú\s,.]+)'
        asegurado_domicilio_pattern = r'Domicilio\s*:\s*([^C]*?)(?=Ciudad|$)'
        asegurado_ciudad_pattern = r'Ciudad\s*:\s*([A-ZÁ-Ú\s,.]+)'
        
        # Patrones RFC y teléfono
        rfc_pattern = r'R\.F\.C\.\s*:\s*([A-Z0-9]{10,13})'
        telefono_pattern = r'Teléfono:\s*(\d{7,11})'
        
        # Patrones zona y condiciones
        zona_pattern = r'Zona Tarificación:\s*Zona\s*(\d+)'
        periodo_siniestro_pattern = r'Período de pago de siniestro\s*(\d+\s*años)'
        
        # Patrones agente y promotor
        agente_clave_pattern = r'Agente\s*:\s*(\d+)'
        agente_nombre_pattern = r'Agente\s*:\s*\d+\s*([A-ZÁ-Ú\s,.]+)'
        promotor_pattern = r'Promotor\s*:\s*(\d+)'
        
        # Patrones datos financieros
        prima_neta_pattern = r'Prima Neta\s*\n?\s*([\d,]+\.\d{2})'
        descuento_pattern = r'Descuento familiar\s*\n?\s*(\d+)'
        cesion_pattern = r'Cesión de Comisión\s*\n?\s*(\d+)'
        recargo_pattern = r'Recargo por pago fraccionado\s*\n?\s*(\d+)'
        derecho_poliza_pattern = r'Derecho de póliza\s*\n?\s*([\d,]+\.\d{2})'
        iva_pattern = r'I\.V\.A\.\s*\n?\s*([\d,]+\.\d{2})'
        prima_total_pattern = r'Prima anual total\s*\n?\s*([\d,]+\.\d{2})'
        
        # Patrones generales para servicios adicionales
        emergencias_pattern = r'Emergencias en el Extranjero\s*\n?\s*([^N]*)'
        medicamentos_pattern = r'Medicamentos fuera del hospital\s*\n?\s*([^N]*)'
        maternidad_pattern = r'Maternidad\s*\n?\s*([^D]*)'
        coaseguro_pattern = r'Coaseguro\s*\n?\s*([0-9]+%)'
        tope_coaseguro_pattern = r'Tope de Coaseguro\s*\n?\s*\$\s*([\d,]+\s*M\.N\.)'
        suma_asegurada_pattern = r'SumaAsegurada\s*\n?\s*\$\s*([\d,]+\s*M\.N\.)'
        deducible_pattern = r'Deducible\s*\n?\s*\$\s*([\d,]+\s*M\.N\.)'
        dental_pattern = r'Protección Dental\s*\n?\s*([^N]*)'
        medico_24_pattern = r'Tu Médico 24 Hrs\s*\n?\s*([^N]*)'
        
        # Patrón específico para la tabla
        tabla_datos_financieros_pattern = r'Prima\s*\n\s*Descuento familiar\s*\n\s*(\d+)\s*\n\s*Cesión de Comisión\s*\n\s*(\d+)\s*\n\s*Prima Neta\s*\n\s*([\d,]+\.\d{2})\s*\n\s*Recargo por pago fraccionado\s*\n\s*(\d+)\s*\n\s*Derecho de póliza\s*\n\s*([\d,]+\.\d{2})\s*\n\s*I\.V\.A\.\s*\n\s*([\d,]+\.\d{2})\s*\n\s*Prima anual total\s*\n\s*([\d,]+\.\d{2})'
        
        # Buscar fechas
        fecha_emision_match = re.search(r'Fecha\s+de\s+Emisi[óo]n\s*[^\d]*(\d{2}/\d{2}/\d{4})', texto_completo, re.IGNORECASE)
        fecha_inicio_match = re.search(r'(?:Vigencia\s+desde|Fecha\s+de\s+inicio\s+de\s+vigencia)\s*[^\d]*(\d{2}/\d{2}/\d{4})', texto_completo, re.IGNORECASE)
        fecha_fin_match = re.search(r'(?:Vigencia\s+hasta|Fecha\s+de\s+fin\s+de\s+vigencia)\s*[^\d]*(\d{2}/\d{2}/\d{4})', texto_completo, re.IGNORECASE)
        
        # Buscar fechas en formato DD/MMM/YYYY
        fecha_emision_alt_match = re.search(r'Fecha\s+de\s+Emisi[óo]n\s*[^\d]*(\d{2}/[A-Za-z]{3}/\d{4})', texto_completo, re.IGNORECASE)
        
        # Buscar formato de vigencia con "A" como separador
        fecha_vigencia_alt_match = re.search(r'Vigencia\s*[^\d]*(\d{2}/[A-Za-z]{3}/\d{4})\s*A\s*(\d{2}/[A-Za-z]{3}/\d{4})', texto_completo, re.IGNORECASE)
        
        # Extraer datos básicos
        matches = {
            "Número de póliza": re.search(poliza_pattern, texto_completo),
            "Solicitud": re.search(solicitud_pattern, texto_completo),
            "Tipo de Plan": re.search(tipo_plan_pattern, texto_completo),
            "Fecha de inicio de vigencia": re.search(fecha_inicio_pattern, texto_completo),
            "Fecha de fin de vigencia": re.search(fecha_fin_pattern, texto_completo),
            "Fecha de emisión": re.search(fecha_emision_pattern, texto_completo),
            "Frecuencia de pago": re.search(frecuencia_pago_pattern, texto_completo),
            "Tipo de pago": re.search(tipo_pago_pattern, texto_completo),
            "Nombre del contratante": re.search(contratante_nombre_pattern, texto_completo),
            "Domicilio del contratante": re.search(contratante_domicilio_pattern, texto_completo),
            "Ciudad del contratante": re.search(contratante_ciudad_pattern, texto_completo),
            "Código Postal": re.search(contratante_cp_pattern, texto_completo),
            "Nombre del asegurado titular": re.search(asegurado_nombre_pattern, texto_completo),
            "Domicilio del asegurado": re.search(asegurado_domicilio_pattern, texto_completo),
            "Ciudad del asegurado": re.search(asegurado_ciudad_pattern, texto_completo),
            "R.F.C.": re.search(rfc_pattern, texto_completo),
            "Teléfono": re.search(telefono_pattern, texto_completo),
            "Zona Tarificación": re.search(zona_pattern, texto_completo),
            "Periodo de pago de siniestro": re.search(periodo_siniestro_pattern, texto_completo),
            "Clave Agente": re.search(agente_clave_pattern, texto_completo),
            "Nombre del agente": re.search(agente_nombre_pattern, texto_completo),
            "Promotor": re.search(promotor_pattern, texto_completo),
            "Prima Neta": re.search(prima_neta_pattern, texto_completo),
            "Descuento familiar": re.search(descuento_pattern, texto_completo),
            "Cesión de Comisión": re.search(cesion_pattern, texto_completo),
            "Recargo por pago fraccionado": re.search(recargo_pattern, texto_completo),
            "Derecho de póliza": re.search(derecho_poliza_pattern, texto_completo),
            "I.V.A.": re.search(iva_pattern, texto_completo),
            "Prima anual total": re.search(prima_total_pattern, texto_completo),
            "Emergencias en el Extranjero": re.search(emergencias_pattern, texto_completo),
            "Medicamentos fuera del hospital": re.search(medicamentos_pattern, texto_completo),
            "Maternidad": re.search(maternidad_pattern, texto_completo),
            "Protección Dental": re.search(dental_pattern, texto_completo),
            "Tu Médico 24 Hrs": re.search(medico_24_pattern, texto_completo),
            "Coaseguro": re.search(coaseguro_pattern, texto_completo),
            "Tope de Coaseguro": re.search(tope_coaseguro_pattern, texto_completo),
            "Suma Asegurada": re.search(suma_asegurada_pattern, texto_completo),
            "Deducible": re.search(deducible_pattern, texto_completo),
        }
        
        # Llenar los datos
        for campo, match in matches.items():
            if match:
                try:
                    if campo in ["Prima Neta", "Prima anual total", "I.V.A.", "Derecho de póliza"]:
                        valor = match.group(1).strip()
                        resultado[campo] = normalizar_numero(valor)
                    elif campo in ["Descuento familiar", "Cesión de Comisión", "Recargo por pago fraccionado"]:
                        valor = match.group(1).strip()
                        resultado[campo] = normalizar_numero(valor)
                    else:
                        resultado[campo] = match.group(1).strip()
                    logging.info(f"Extraído {campo}: {resultado[campo]}")
                except (IndexError, AttributeError) as e:
                    logging.warning(f"Error extrayendo {campo}: {e}")
        
        # Procesar tabla de datos financieros completa si existe
        match_tabla = re.search(tabla_datos_financieros_pattern, texto_completo)
        if match_tabla:
            resultado["Descuento familiar"] = normalizar_numero(match_tabla.group(1))
            resultado["Cesión de Comisión"] = normalizar_numero(match_tabla.group(2))
            resultado["Prima Neta"] = normalizar_numero(match_tabla.group(3))
            resultado["Recargo por pago fraccionado"] = normalizar_numero(match_tabla.group(4))
            resultado["Derecho de póliza"] = normalizar_numero(match_tabla.group(5))
            resultado["I.V.A."] = normalizar_numero(match_tabla.group(6))
            resultado["Prima anual total"] = normalizar_numero(match_tabla.group(7))
            logging.info(f"Datos financieros extraídos del patrón completo de tabla")
        
        # Búsqueda alternativa para extraer datos específicos del formato AXA salud familiar
        for linea in texto_completo.split('\n'):
            if "Póliza" in linea and resultado["Número de póliza"] == "0":
                match = re.search(r'(\d{5,}[A-Z0-9]+)', linea)
                if match:
                    resultado["Número de póliza"] = match.group(1)
                    logging.info(f"Número de póliza extraído (alt): {resultado['Número de póliza']}")
            
            # Buscar agente si no lo encontramos aún
            if "Agente" in linea and ":" in linea and resultado["Clave Agente"] == "0":
                match = re.search(r'Agente\s*:?\s*(\d+)', linea)
                if match:
                    resultado["Clave Agente"] = match.group(1)
                    logging.info(f"Clave Agente extraída (alt): {resultado['Clave Agente']}")
            
            # Buscar datos financieros alternativos
            for nombre_campo in ["Descuento familiar", "Cesión de Comisión", "Prima Neta", 
                                "Recargo por pago fraccionado", "Derecho de póliza", "I.V.A.", "Prima anual total"]:
                if nombre_campo in linea and resultado[nombre_campo] == "0":
                    match = re.search(rf'{re.escape(nombre_campo)}\s+(\d+[,\d]*\.\d{2}|\d+)', linea)
                    if match:
                        resultado[nombre_campo] = normalizar_numero(match.group(1))
                        logging.info(f"{nombre_campo} extraído (alt): {resultado[nombre_campo]}")
        
        # Extraer coberturas incluidas
        cobertura_pattern = r'Incluidos en Básica\s+(.*?)(?=Coberturas adicionales con costo|$)'
        cobertura_match = re.search(cobertura_pattern, texto_completo, re.DOTALL | re.IGNORECASE)
        if cobertura_match:
            coberturas_incluidas.append({
                "Nombre": "Cobertura Básica",
                "Suma Asegurada": resultado.get("Suma Asegurada", "N/A"),
                "Deducible": resultado.get("Deducible", "N/A"),
                "Coaseguro": resultado.get("Coaseguro", "N/A")
            })
        
        # Añadir las coberturas y servicios al resultado
        resultado["Coberturas Incluidas"] = coberturas_incluidas
        resultado["Coberturas Adicionales"] = coberturas_adicionales
        resultado["Servicios con Costo"] = servicios_costo
        
        # URL específica para variante F
        resultado["Url"] = "https://rinoapps.com/condiciones/salud_familiar_variantef.pdf"
        
        # Si hay campos específicos que aún no hemos encontrado, buscamos en la imagen
        # Si no tenemos nombre del contratante pero sí hay datos en la imagen
        if resultado["Nombre del contratante"] == "0":
            nombre_contratante_alt = re.search(r'Nombre\s*\n\s*([A-ZÁ-Ú\s,.]+)', texto_completo)
            if nombre_contratante_alt:
                resultado["Nombre del contratante"] = nombre_contratante_alt.group(1).strip()
                logging.info(f"Nombre del contratante extraído (alt2): {resultado['Nombre del contratante']}")
        
        # Si no tenemos datos del asegurado, usar los del contratante
        if resultado["Nombre del asegurado titular"] == "0" and resultado["Nombre del contratante"] != "0":
            resultado["Nombre del asegurado titular"] = resultado["Nombre del contratante"]
            logging.info(f"Nombre del asegurado titular asumido como el contratante: {resultado['Nombre del asegurado titular']}")
        
        # Extraer datos básicos
        if "Fecha de emisión" not in resultado or resultado["Fecha de emisión"] == "0":
            # Asignar fechas extraídas
            if fecha_emision_match:
                resultado['Fecha de emisión'] = fecha_emision_match.group(1)
                logging.info(f"Fecha de emisión extraída: {resultado['Fecha de emisión']}")
            elif fecha_emision_alt_match:
                resultado['Fecha de emisión'] = fecha_emision_alt_match.group(1)
                logging.info(f"Fecha de emisión extraída (formato alt): {resultado['Fecha de emisión']}")
        
        if "Fecha de inicio de vigencia" not in resultado or resultado["Fecha de inicio de vigencia"] == "0":
            if fecha_inicio_match:
                resultado['Fecha de inicio de vigencia'] = fecha_inicio_match.group(1)
                logging.info(f"Fecha de inicio de vigencia extraída: {resultado['Fecha de inicio de vigencia']}")
            elif fecha_vigencia_alt_match:
                resultado['Fecha de inicio de vigencia'] = fecha_vigencia_alt_match.group(1)
                logging.info(f"Fecha de inicio de vigencia extraída (formato alt): {resultado['Fecha de inicio de vigencia']}")
                
        if "Fecha de fin de vigencia" not in resultado or resultado["Fecha de fin de vigencia"] == "0":
            if fecha_fin_match:
                resultado['Fecha de fin de vigencia'] = fecha_fin_match.group(1)
                logging.info(f"Fecha de fin de vigencia extraída: {resultado['Fecha de fin de vigencia']}")
            elif fecha_vigencia_alt_match:
                resultado['Fecha de fin de vigencia'] = fecha_vigencia_alt_match.group(2)
                logging.info(f"Fecha de fin de vigencia extraída (formato alt): {resultado['Fecha de fin de vigencia']}")
    
    except Exception as e:
        logging.error(f"Error procesando PDF de Gastos Médicos Mayores Familiar Variante F: {str(e)}", exc_info=True)

    return resultado

def generar_markdown(datos: Dict, ruta_salida: str = "salud_familiar_variantef.md") -> None:
    """
    Genera un archivo markdown con los datos extraídos estructurados.
    """
    try:
        # Organizar datos por categorías
        info_general = {
            "Tipo de Documento": "Póliza de Gastos Médicos Mayores Familiar (Variante F)",
            "Número de Póliza": datos["Número de póliza"] if datos["Número de póliza"] != "0" else "Por determinar",
            "Solicitud": datos["Solicitud"] if datos["Solicitud"] != "0" else "Por determinar",
            "Tipo de Plan": datos["Tipo de Plan"] if datos["Tipo de Plan"] != "0" else "Por determinar",
            "Moneda": datos["Moneda"] if datos["Moneda"] != "0" else "Por determinar"
        }
        
        datos_contratante = {
            "Nombre del Contratante": datos["Nombre del contratante"] if datos["Nombre del contratante"] != "0" else "Por determinar",
            "Domicilio": datos["Domicilio del contratante"] if datos["Domicilio del contratante"] != "0" else "Por determinar",
            "Ciudad": datos["Ciudad del contratante"] if datos["Ciudad del contratante"] != "0" else "Por determinar",
            "Estado": datos["Estado"] if datos["Estado"] != "0" else "Por determinar",
            "Código Postal": datos["Código Postal"] if datos["Código Postal"] != "0" else "Por determinar",
            "R.F.C.": datos["R.F.C."] if datos["R.F.C."] != "0" else "Por determinar",
            "Teléfono": datos["Teléfono"] if datos["Teléfono"] != "0" else "Por determinar"
        }
        
        fechas = {
            "Fecha de Emisión": datos["Fecha de emisión"] if datos["Fecha de emisión"] != "0" else "Por determinar",
            "Fecha de Inicio de Vigencia": datos["Fecha de inicio de vigencia"] if datos["Fecha de inicio de vigencia"] != "0" else "Por determinar",
            "Fecha de Fin de Vigencia": datos["Fecha de fin de vigencia"] if datos["Fecha de fin de vigencia"] != "0" else "Por determinar",
            "Frecuencia de Pago": datos["Frecuencia de pago"] if datos["Frecuencia de pago"] != "0" else "Por determinar"
        }
        
        condiciones = {
            "Suma Asegurada": datos["Suma Asegurada"] if datos["Suma Asegurada"] != "0" else "Por determinar",
            "Deducible": datos["Deducible"] if datos["Deducible"] != "0" else "Por determinar",
            "Coaseguro": datos["Coaseguro"] if datos["Coaseguro"] != "0" else "Por determinar",
            "Tope de Coaseguro": datos["Tope de Coaseguro"] if datos["Tope de Coaseguro"] != "0" else "Por determinar"
        }
        
        info_financiera = {
            "Prima Neta": datos["Prima Neta"] if datos["Prima Neta"] != "0" else "Por determinar",
            "Gastos de Expedición": datos["Gastos de Expedición"] if datos["Gastos de Expedición"] != "0" else "Por determinar",
            "Prima base I.V.A.": datos["Prima base I.V.A."] if datos["Prima base I.V.A."] != "0" else "Por determinar",
            "I.V.A.": datos["I.V.A."] if datos["I.V.A."] != "0" else "Por determinar",
            "Prima Total": datos["Prima anual total"] if datos["Prima anual total"] != "0" else "Por determinar",
            "Descuento familiar": datos["Descuento familiar"] if datos["Descuento familiar"] != "0" else "Por determinar",
            "Cesión de Comisión": datos["Cesión de Comisión"] if datos["Cesión de Comisión"] != "0" else "Por determinar",
            "Recargo por pago fraccionado": datos["Recargo por pago fraccionado"] if datos["Recargo por pago fraccionado"] != "0" else "Por determinar"
        }
        
        # Construir el markdown
        md_content = "# Datos Extraídos de Póliza de Gastos Médicos Mayores Familiar (Variante F)\n\n"
        
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
        
        # Coberturas Amparadas
        md_content += "## Coberturas Amparadas\n"
        if "Coberturas Amparadas" in datos and datos["Coberturas Amparadas"]:
            for cobertura in datos["Coberturas Amparadas"]:
                md_content += f"- **{cobertura['Nombre']}**: {cobertura['Límites']}\n"
        else:
            md_content += "No se encontraron coberturas amparadas específicas.\n"
        md_content += "\n"
        
        md_content += "Este documento es una póliza de Gastos Médicos Mayores Familiar (Variante F). Los valores \"Por determinar\" indican campos que no pudieron ser claramente identificados en el documento original PDF."
        
        # Guardar el archivo markdown
        with open(ruta_salida, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logging.info(f"Archivo markdown generado en {ruta_salida}")
        
    except Exception as e:
        logging.error(f"Error generando archivo markdown: {str(e)}", exc_info=True)

def guardar_a_json(datos: Dict, ruta_salida: str = "salud_familiar_variantef.json") -> None:
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
    Procesa un archivo PDF de Gastos Médicos Mayores Familiar (Variante F) y guarda los resultados en markdown y JSON.
    
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
        datos = extraer_datos_poliza_salud_familiar_variantef(ruta_pdf)
        
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
        print("Uso: python data_ia_general_salud_familiar_variantef.py <ruta_pdf> [directorio_salida]") 