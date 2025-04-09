import fitz
import re
import logging
import os
import json
from typing import Dict, Optional
from endosos_autos_a import extraer_datos_endoso_a
from data_ia_general_vida import procesar_archivo
from data_ia_general_vida_individual import procesar_archivo as procesar_archivo_individual
from data_ia_general_protgt_ordinario import procesar_archivo as procesar_archivo_protgt_ordinario
from data_ia_general_protgt_ppr import procesar_archivo as procesar_archivo_aliados_ppr
from data_ia_general_protgt_mn import procesar_archivo as procesar_archivo_protgt_temporal_mn
from data_ia_general_vida_protgt import procesar_archivo as procesar_archivo_vida_protgt
from data_ia_general_proteccion_efectiva import procesar_archivo as procesar_archivo_proteccion_efectiva
from data_ia_general_protgt_pyme import procesar_archivo as procesar_archivo_protgt_pyme

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extrae el texto de un archivo PDF.
    
    Args:
        pdf_path (str): Ruta al archivo PDF
        
    Returns:
        str: Texto extraído del PDF
    """
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        logger.error(f"Error al extraer texto del PDF: {str(e)}")
        return ""

def detect_document_type(text: str) -> str:
    """
    Detecta el tipo de documento basado en el contenido del texto.
    
    Args:
        text (str): Texto extraído del PDF
        
    Returns:
        str: Tipo de documento detectado ('ENDOSO_A', 'POLIZA_VIDA', 'POLIZA_VIDA_INDIVIDUAL', 
                                         'PROTEGETE_ORDINARIO', 'ALIADOS_PPR', 'PROTGT_TEMPORAL_MN', 
                                         'VIDA_PROTGT', 'PROTECCION_EFECTIVA', 'PROTGT_PYME', 'DESCONOCIDO')
    """
    # Normalizar el texto
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    
    # Patrones para identificar Aliados+ PPR (MÁXIMA PRIORIDAD)
    patrones_aliados_ppr = [
        r"aliados\s*\+\s*ppr",
        r"aliados\s*\+",
        r"vida y ahorro",
        r"carátula de póliza.*aliados",
        r"aliados\+.*car[áa]tula",
        r"aliados.*ppr",
        r"póliza.*ahorro",
        r"vida.*ahorro",
        r"seguro.*ahorro",
        r"aliados\s*mas",
        r"ahorro.*programado",
        r"seguro.*aliados"
    ]
    
    # Patrones para identificar VIDA PROTGT
    patrones_vida_protgt = [
        r"vida protgt",
        r"protgt cobertura",
        r"cobertura conyugal",
        r"caratula de p[óo]liza.*vida\s*protgt",
        r"p[óo]liza.*vida\s*protgt"
    ]
    
    # Patrones para identificar Protegete Temporal MN
    patrones_protgt_temporal_mn = [
        r"vida protgt temporal mn",
        r"protgt temporal mn",
        r"temporal mn",
        r"carátula de póliza.*temporal mn",
        r"vida protgt temporal"
    ]
    
    # Patrones para identificar Protección Efectiva
    patrones_proteccion_efectiva = [
        r"protección efectiva",
        r"carátula de póliza.*protección efectiva",
        r"temporal a 1 año",
        r"proteccion efectiva",
        r"caratula de poliza.*proteccion efectiva",
        r"hoja 1 de 2.*protección efectiva"
    ]
    
    # Patrones para identificar Plan Protege PYME
    patrones_protgt_pyme = [
        r"plan protege pyme",
        r"carátula de póliza.*plan protege pyme",
        r"protege pyme",
        r"grupo empresarial",
        r"características del grupo asegurado",
        r"regla para determinar la suma asegurada"
    ]
    
    # Patrones para identificar Protegete Ordinario
    patrones_protegete_ordinario = [
        r"vida protgt ordinario",
        r"protgt ordinario de vida",
        r"vida protegete ordinario",
        r"protegete ordinario de vida"
    ]
    
    # Patrones para identificar póliza de vida individual
    patrones_vida_individual = [
        r"vida individual",
        r"seguro individual",
        r"p[óo]liza individual",
        r"vida inteligente",
        r"seguro de vida individual"
    ]
    
    # Patrones para identificar póliza de vida
    patrones_vida = [
        r"ordinario de vida",
        r"seguro de vida",
        r"p[óo]liza de vida",
        r"beneficiario(s)?\s+del\s+seguro",
        r"suma\s+asegurada\s+por\s+fallecimiento"
    ]
    
    # Patrones para identificar endoso tipo A
    patrones_endoso_a = [
        r"endoso\s+tipo\s+a",
        r"endoso\s+de\s+modificación\s+de\s+datos",
        r"modificación\s+de\s+datos\s+del\s+asegurado",
        r"cambio\s+de\s+datos\s+del\s+asegurado",
        r"endoso\s+de\s+modificación",
        r"modificación\s+de\s+datos",
        r"cambio\s+de\s+datos",
        r"endoso\s+de\s+datos",
        r"endoso\s+modificación",
        r"endoso\s+tipo\s+a\s+modificación"
    ]
    
    # **Reordenamiento de la lógica de detección**
    
    # 1. Buscar patrones de Aliados+ PPR primero
    for patron in patrones_aliados_ppr:
        if re.search(patron, text):
            logger.info(f"Detectada póliza Aliados+ PPR con patrón: {patron}")
            return "ALIADOS_PPR"
            
    # 2. Buscar patrones de VIDA PROTGT
    for patron in patrones_vida_protgt:
        if re.search(patron, text):
            logger.info(f"Detectada póliza VIDA PROTGT con patrón: {patron}")
            return "VIDA_PROTGT"
            
    # 3. Buscar patrones de Protegete Temporal MN
    for patron in patrones_protgt_temporal_mn:
        if re.search(patron, text):
            logger.info(f"Detectada póliza Protegete Temporal MN con patrón: {patron}")
            return "PROTGT_TEMPORAL_MN"
            
    # 4. Buscar patrones de Protección Efectiva
    for patron in patrones_proteccion_efectiva:
        if re.search(patron, text):
            logger.info(f"Detectada póliza Protección Efectiva con patrón: {patron}")
            return "PROTECCION_EFECTIVA"
    
    # 5. Buscar patrones de Plan Protege PYME
    for patron in patrones_protgt_pyme:
        if re.search(patron, text):
            logger.info(f"Detectada póliza Plan Protege PYME con patrón: {patron}")
            return "PROTGT_PYME"
            
    # 6. Buscar patrones de Protegete Ordinario
    for patron in patrones_protegete_ordinario:
        if re.search(patron, text):
            logger.info(f"Detectada póliza Protegete Ordinario con patrón: {patron}")
            return "PROTEGETE_ORDINARIO"
            
    # 7. Buscar patrones de póliza de vida individual
    for patron in patrones_vida_individual:
        if re.search(patron, text):
            logger.info(f"Detectada póliza de vida individual con patrón: {patron}")
            return "POLIZA_VIDA_INDIVIDUAL"
            
    # 8. Buscar patrones de póliza de vida (genérico)
    for patron in patrones_vida:
        if re.search(patron, text):
            logger.info(f"Detectada póliza de vida con patrón: {patron}")
            return "POLIZA_VIDA"
            
    # 9. Buscar patrones de endoso tipo A (al final)
    for patron in patrones_endoso_a:
        if re.search(patron, text):
            logger.info(f"Detectado endoso tipo A con patrón: {patron}")
            return "ENDOSO_A"
    
    # Si no se encuentra ningún patrón, tipo desconocido
    logger.info("No se encontró patrón específico, documento de tipo desconocido")
    return "DESCONOCIDO"

def detect_endoso_type(text: str) -> Optional[str]:
    """
    Detecta el tipo de endoso basado en el contenido del texto.
    
    Args:
        text (str): Texto extraído del PDF
        
    Returns:
        Optional[str]: Tipo de endoso detectado o None si no se puede determinar
    """
    # Esta función se mantiene para compatibilidad con el código existente
    doc_type = detect_document_type(text)
    if doc_type == "ENDOSO_A":
        return "A"
    return None

def validate_endoso(pdf_path: str) -> Dict:
    """
    Valida el tipo de documento y extrae los datos correspondientes.
    
    Args:
        pdf_path (str): Ruta al archivo PDF
        
    Returns:
        dict: Diccionario con el resultado de la validación y los datos extraídos
    """
    doc = None # Inicializar doc a None
    texto = "" # Inicializar texto
    try:
        logger.info(f"Intentando abrir PDF: {pdf_path} con fitz (PyMuPDF)...")
        doc = fitz.open(pdf_path)
        logger.info(f"PDF {pdf_path} abierto correctamente con fitz.")
        
        if doc.page_count < 1:
            logger.error(f"El PDF {pdf_path} no tiene páginas.")
            return {"error": "El PDF no tiene páginas"}
            
        # **Extraer texto para detección SIEMPRE con fitz**
        logger.info(f"Extrayendo texto con fitz para detección en {pdf_path}...")
        for page_num in range(min(doc.page_count, 2)): # Leer las primeras 2 páginas para detección
             page = doc.load_page(page_num)
             texto += page.get_text()
             
        if not texto:
             logger.error(f"fitz no pudo extraer texto de las primeras páginas de {pdf_path}")
             return {"error": "No se pudo extraer texto del PDF para detección"}
        
        # Detectar el tipo de documento usando el texto extraído con fitz
        tipo_documento = detect_document_type(texto) 
        
        # Procesar según el tipo de documento
        if tipo_documento == "ENDOSO_A":
            logger.info(f"Endoso tipo A detectado para {pdf_path}. Procediendo a extraer datos financieros.")
            datos_financieros = extraer_datos_endoso_a(pdf_path)
            if datos_financieros:
                logger.info(f"Datos financieros extraídos exitosamente para {pdf_path}.")
                # Asegurarse de que todos los datos financieros incluyan prima_mensual
                datos_financieros_completos = {
                    "prima_neta": datos_financieros.get("prima_neta", "0"),
                    "gastos_expedicion": datos_financieros.get("gastos_expedicion", "0"),
                    "iva": datos_financieros.get("iva", "0"),
                    "precio_total": datos_financieros.get("precio_total", "0"),
                    "tasa_financiamiento": datos_financieros.get("tasa_financiamiento", "0"),
                    "prima_mensual": datos_financieros.get("prima_mensual", "0")
                }
                return {
                    "tipo_documento": "ENDOSO_A",
                    "tipo_endoso": "A",
                    "descripcion": "MODIFICACIÓN DE DATOS",
                    "datos_financieros": datos_financieros_completos
                }
            else:
                logger.error(f"Se detectó Endoso A para {pdf_path}, pero no se pudieron extraer los datos financieros.")
                return {"error": "Se detectó Endoso A, pero no se pudieron extraer los datos financieros"}
        
        elif tipo_documento == "ALIADOS_PPR":
            logger.info(f"Póliza Aliados+ PPR detectada para {pdf_path}. Procediendo a extraer datos.")
            
            # Crear directorio de salida temporal si no existe
            output_dir = os.path.join(os.path.dirname(pdf_path), "output")
            os.makedirs(output_dir, exist_ok=True)
            
            # Procesar el archivo y obtener datos con el script para pólizas Aliados+ PPR
            datos_aliados_ppr = procesar_archivo_aliados_ppr(pdf_path, output_dir)
            
            if datos_aliados_ppr:
                logger.info(f"Datos de póliza Aliados+ PPR extraídos exitosamente para {pdf_path}.")
                # Convertir los datos a formato financiero esperado por el frontend
                datos_financieros = {
                    "prima_neta": datos_aliados_ppr.get("Prima Neta", "0"),
                    "gastos_expedicion": "0",  # No aplica para este tipo de pólizas
                    "iva": datos_aliados_ppr.get("I.V.A.", "0"),
                    "precio_total": datos_aliados_ppr.get("Prima anual total", "0"),
                    "tasa_financiamiento": "0",  # No aplica para este tipo de pólizas
                    "prima_mensual": datos_aliados_ppr.get("Prima mensual", "0")
                }
                
                return {
                    "tipo_documento": "POLIZA_ALIADOS_PPR",
                    "descripcion": "PÓLIZA ALIADOS+ PPR",
                    "datos_financieros": datos_financieros,
                    "datos_completos": datos_aliados_ppr
                }
            else:
                logger.error(f"Se detectó póliza Aliados+ PPR para {pdf_path}, pero no se pudieron extraer los datos.")
                return {"error": "Se detectó póliza Aliados+ PPR, pero no se pudieron extraer los datos"}
        
        elif tipo_documento == "PROTGT_TEMPORAL_MN":
            logger.info(f"Póliza Protegete Temporal MN detectada para {pdf_path}. Procediendo a extraer datos.")
            
            # Crear directorio de salida temporal si no existe
            output_dir = os.path.join(os.path.dirname(pdf_path), "output")
            os.makedirs(output_dir, exist_ok=True)
            
            # Procesar el archivo y obtener datos con el script para pólizas Protegete Temporal MN
            datos_protgt_temporal_mn = procesar_archivo_protgt_temporal_mn(pdf_path, output_dir)
            
            if datos_protgt_temporal_mn:
                logger.info(f"Datos de póliza Protegete Temporal MN extraídos exitosamente para {pdf_path}.")
                # Convertir los datos a formato financiero esperado por el frontend
                datos_financieros = {
                    "prima_neta": datos_protgt_temporal_mn.get("Prima Neta", "0"),
                    "gastos_expedicion": "0",  # No aplica para este tipo de pólizas
                    "iva": datos_protgt_temporal_mn.get("I.V.A.", "0"),
                    "precio_total": datos_protgt_temporal_mn.get("Prima anual total", "0"),
                    "tasa_financiamiento": "0",  # No aplica para este tipo de pólizas
                    "prima_mensual": datos_protgt_temporal_mn.get("Prima mensual", "0")
                }
                
                return {
                    "tipo_documento": "POLIZA_PROTGT_TEMPORAL_MN",
                    "descripcion": "PÓLIZA PROTGT TEMPORAL MN",
                    "datos_financieros": datos_financieros,
                    "datos_completos": datos_protgt_temporal_mn
                }
            else:
                logger.error(f"Se detectó póliza Protegete Temporal MN para {pdf_path}, pero no se pudieron extraer los datos.")
                return {"error": "Se detectó póliza Protegete Temporal MN, pero no se pudieron extraer los datos"}
        
        elif tipo_documento == "PROTEGETE_ORDINARIO":
            logger.info(f"Póliza Protegete Ordinario detectada para {pdf_path}. Procediendo a extraer datos.")
            
            # Crear directorio de salida temporal si no existe
            output_dir = os.path.join(os.path.dirname(pdf_path), "output")
            os.makedirs(output_dir, exist_ok=True)
            
            # Procesar el archivo y obtener datos con el script para pólizas Protegete Ordinario
            datos_protegete = procesar_archivo_protgt_ordinario(pdf_path, output_dir)
            
            if datos_protegete:
                logger.info(f"Datos de póliza Protegete Ordinario extraídos exitosamente para {pdf_path}.")
                # Convertir los datos a formato financiero esperado por el frontend
                datos_financieros = {
                    "prima_neta": datos_protegete.get("Prima Neta", "0"),
                    "gastos_expedicion": "0",  # No aplica para este tipo de pólizas
                    "iva": datos_protegete.get("I.V.A.", "0"),
                    "precio_total": datos_protegete.get("Prima anual total", "0"),
                    "tasa_financiamiento": "0",  # No aplica para este tipo de pólizas
                    "prima_mensual": datos_protegete.get("Prima mensual", "0")
                }
                
                return {
                    "tipo_documento": "POLIZA_VIDA",
                    "descripcion": "PÓLIZA PROTEGETE ORDINARIO",
                    "datos_financieros": datos_financieros,
                    "datos_completos": datos_protegete
                }
            else:
                logger.error(f"Se detectó póliza Protegete Ordinario para {pdf_path}, pero no se pudieron extraer los datos.")
                return {"error": "Se detectó póliza Protegete Ordinario, pero no se pudieron extraer los datos"}
        
        elif tipo_documento == "POLIZA_VIDA_INDIVIDUAL":
            logger.info(f"Póliza de vida individual detectada para {pdf_path}. Procediendo a extraer datos.")
            
            # Crear directorio de salida temporal si no existe
            output_dir = os.path.join(os.path.dirname(pdf_path), "output")
            os.makedirs(output_dir, exist_ok=True)
            
            # Procesar el archivo y obtener datos con el script para pólizas de vida individual
            datos_vida = procesar_archivo_individual(pdf_path, output_dir)
            
            if datos_vida:
                logger.info(f"Datos de póliza de vida individual extraídos exitosamente para {pdf_path}.")
                # Convertir los datos a formato financiero esperado por el frontend
                datos_financieros = {
                    "prima_neta": datos_vida.get("Prima Neta", "0"),
                    "gastos_expedicion": "0",  # No aplica para pólizas de vida
                    "iva": datos_vida.get("I.V.A.", "0"),
                    "precio_total": datos_vida.get("Prima anual total", "0"),
                    "tasa_financiamiento": "0",  # No aplica para pólizas de vida
                    "prima_mensual": datos_vida.get("Prima mensual", "0")
                }
                
                return {
                    "tipo_documento": "POLIZA_VIDA",
                    "descripcion": "PÓLIZA DE VIDA INDIVIDUAL",
                    "datos_financieros": datos_financieros,
                    "datos_completos": datos_vida
                }
            else:
                logger.error(f"Se detectó póliza de vida individual para {pdf_path}, pero no se pudieron extraer los datos.")
                return {"error": "Se detectó póliza de vida individual, pero no se pudieron extraer los datos"}
        
        elif tipo_documento == "POLIZA_VIDA":
            logger.info(f"Póliza de vida detectada para {pdf_path}. Procediendo a extraer datos.")
            
            # Crear directorio de salida temporal si no existe
            output_dir = os.path.join(os.path.dirname(pdf_path), "output")
            os.makedirs(output_dir, exist_ok=True)
            
            # Procesar el archivo y obtener datos
            datos_vida = procesar_archivo(pdf_path, output_dir)
            
            if datos_vida:
                logger.info(f"Datos de póliza de vida extraídos exitosamente para {pdf_path}.")
                # Convertir los datos a formato financiero esperado por el frontend
                datos_financieros = {
                    "prima_neta": datos_vida.get("Prima Neta", "0"),
                    "gastos_expedicion": "0",  # No aplica para pólizas de vida
                    "iva": datos_vida.get("I.V.A.", "0"),
                    "precio_total": datos_vida.get("Prima anual total", "0"),
                    "tasa_financiamiento": "0",  # No aplica para pólizas de vida
                    "prima_mensual": datos_vida.get("Prima mensual", "0")
                }
                
                return {
                    "tipo_documento": "POLIZA_VIDA",
                    "descripcion": "PÓLIZA DE VIDA",
                    "datos_financieros": datos_financieros,
                    "datos_completos": datos_vida
                }
            else:
                logger.error(f"Se detectó póliza de vida para {pdf_path}, pero no se pudieron extraer los datos.")
                return {"error": "Se detectó póliza de vida, pero no se pudieron extraer los datos"}
        
        elif tipo_documento == "VIDA_PROTGT":
            logger.info(f"Póliza VIDA PROTGT detectada para {pdf_path}. Procediendo a extraer datos.")
            
            # Crear directorio de salida temporal si no existe
            output_dir = os.path.join(os.path.dirname(pdf_path), "output")
            os.makedirs(output_dir, exist_ok=True)
            
            # Procesar el archivo y obtener datos con el script para pólizas VIDA PROTGT
            datos_vida_protgt = procesar_archivo_vida_protgt(pdf_path, output_dir)
            
            if datos_vida_protgt:
                logger.info(f"Datos de póliza VIDA PROTGT extraídos exitosamente para {pdf_path}.")
                # Convertir los datos a formato financiero esperado por el frontend
                datos_financieros = {
                    "prima_neta": datos_vida_protgt.get("Prima Neta", "0"),
                    "gastos_expedicion": "0",  # No aplica para este tipo de pólizas
                    "iva": datos_vida_protgt.get("I.V.A.", "0"),
                    "precio_total": datos_vida_protgt.get("Prima anual total", "0"),
                    "tasa_financiamiento": "0",  # No aplica para este tipo de pólizas
                    "prima_mensual": datos_vida_protgt.get("Prima mensual", "0")
                }
                
                return {
                    "tipo_documento": "POLIZA_VIDA_PROTGT",
                    "descripcion": "PÓLIZA VIDA PROTGT",
                    "datos_financieros": datos_financieros,
                    "datos_completos": datos_vida_protgt
                }
            else:
                logger.error(f"Se detectó póliza VIDA PROTGT para {pdf_path}, pero no se pudieron extraer los datos.")
                return {"error": "Se detectó póliza VIDA PROTGT, pero no se pudieron extraer los datos"}
        
        elif tipo_documento == "PROTECCION_EFECTIVA":
            logger.info(f"Póliza Protección Efectiva detectada para {pdf_path}. Procediendo a extraer datos.")
            
            # Crear directorio de salida temporal si no existe
            output_dir = os.path.join(os.path.dirname(pdf_path), "output")
            os.makedirs(output_dir, exist_ok=True)
            
            # Procesar el archivo y obtener datos con el script para pólizas Protección Efectiva
            datos_proteccion_efectiva = procesar_archivo_proteccion_efectiva(pdf_path, output_dir)
            
            if datos_proteccion_efectiva:
                logger.info(f"Datos de póliza Protección Efectiva extraídos exitosamente para {pdf_path}.")
                # Convertir los datos a formato financiero esperado por el frontend
                datos_financieros = {
                    "prima_neta": datos_proteccion_efectiva.get("Prima Neta", "0"),
                    "gastos_expedicion": "0",  # No aplica para este tipo de pólizas
                    "iva": datos_proteccion_efectiva.get("I.V.A.", "0"),
                    "precio_total": datos_proteccion_efectiva.get("Prima anual total", "0"),
                    "tasa_financiamiento": "0",  # No aplica para este tipo de pólizas
                    "prima_mensual": datos_proteccion_efectiva.get("Prima mensual", "0")
                }
                
                return {
                    "tipo_documento": "POLIZA_VIDA",
                    "descripcion": "PÓLIZA PROTECCION EFECTIVA",
                    "datos_financieros": datos_financieros,
                    "datos_completos": datos_proteccion_efectiva
                }
            else:
                logger.error(f"Se detectó póliza Protección Efectiva para {pdf_path}, pero no se pudieron extraer los datos.")
                return {"error": "Se detectó póliza Protección Efectiva, pero no se pudieron extraer los datos"}
        
        elif tipo_documento == "PROTGT_PYME":
            logger.info(f"Póliza Plan Protege PYME detectada para {pdf_path}. Procediendo a extraer datos.")
            
            # Crear directorio de salida temporal si no existe
            output_dir = os.path.join(os.path.dirname(pdf_path), "output")
            os.makedirs(output_dir, exist_ok=True)
            
            # Procesar el archivo y obtener datos con el script para pólizas Plan Protege PYME
            datos_protgt_pyme = procesar_archivo_protgt_pyme(pdf_path, output_dir)
            
            if datos_protgt_pyme:
                logger.info(f"Datos de póliza Plan Protege PYME extraídos exitosamente para {pdf_path}.")
                # Convertir los datos a formato financiero esperado por el frontend
                datos_financieros = {
                    "prima_neta": datos_protgt_pyme.get("Prima Neta", "0"),
                    "gastos_expedicion": "0",  # No aplica para este tipo de pólizas
                    "iva": datos_protgt_pyme.get("I.V.A.", "0"),
                    "precio_total": datos_protgt_pyme.get("Prima anual total", "0"),
                    "tasa_financiamiento": "0",  # No aplica para este tipo de pólizas
                    "prima_mensual": datos_protgt_pyme.get("Prima mensual", "0")
                }
                
                return {
                    "tipo_documento": "POLIZA_VIDA",
                    "descripcion": "PÓLIZA PLAN PROTEGE PYME",
                    "datos_financieros": datos_financieros,
                    "datos_completos": datos_protgt_pyme
                }
            else:
                logger.error(f"Se detectó póliza Plan Protege PYME para {pdf_path}, pero no se pudieron extraer los datos.")
                return {"error": "Se detectó póliza Plan Protege PYME, pero no se pudieron extraer los datos"}
        
        else:
            logger.warning(f"Tipo de documento no soportado o desconocido para {pdf_path}")
            return {"error": "Tipo de documento no soportado o desconocido"}
            
    except Exception as e:
        logger.error(f"Error general al validar documento {pdf_path}: {str(e)}", exc_info=True)
        return {"error": f"Error interno al procesar el PDF: {str(e)}"}
    finally:
        if doc:
            logger.info(f"Cerrando documento PDF: {pdf_path}")
            doc.close()

if __name__ == "__main__":
    # Ejemplo de uso
    pdf_path = "ruta/al/documento.pdf"  # Reemplazar con la ruta real
    resultado = validate_endoso(pdf_path)
    print(resultado) 