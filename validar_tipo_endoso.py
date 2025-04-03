import fitz
import re
import logging
import os
import json
from typing import Dict, Optional
from endosos_autos_a import extraer_datos_endoso_a
from data_ia_general_vida import procesar_archivo
from data_ia_general_vida_individual import procesar_archivo as procesar_archivo_individual

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
        str: Tipo de documento detectado ('ENDOSO_A', 'POLIZA_VIDA', 'POLIZA_VIDA_INDIVIDUAL', 'DESCONOCIDO')
    """
    # Normalizar el texto
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    
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
    
    # Buscar patrones de póliza de vida individual
    for patron in patrones_vida_individual:
        if re.search(patron, text):
            logger.info(f"Detectada póliza de vida individual con patrón: {patron}")
            return "POLIZA_VIDA_INDIVIDUAL"
    
    # Buscar patrones de póliza de vida
    for patron in patrones_vida:
        if re.search(patron, text):
            logger.info(f"Detectada póliza de vida con patrón: {patron}")
            return "POLIZA_VIDA"
    
    # Buscar patrones de endoso tipo A
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
    try:
        # --- Añadir log específico para la apertura ---
        logger.info(f"Intentando abrir PDF: {pdf_path} con fitz (PyMuPDF)...")
        # Abrir el PDF
        doc = fitz.open(pdf_path)
        logger.info(f"PDF {pdf_path} abierto correctamente con fitz.")
        # --- Fin del cambio ---
        
        if doc.page_count < 1:
            logger.error(f"El PDF {pdf_path} no tiene páginas.")
            return {"error": "El PDF no tiene páginas"}
            
        # Extraer texto para la detección
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(pdf_path)
            if len(reader.pages) > 0:
                 texto = reader.pages[0].extract_text() # Texto extraído por PyPDF2
            else:
                 texto = "" # O manejar error si prefieres
        except Exception as e_pypdf:
             logger.warning(f"PyPDF2 no pudo extraer texto de {pdf_path}: {e_pypdf}")
             # Fallback a fitz si PyPDF2 falla
             logger.info(f"Intentando extraer texto con fitz para {pdf_path}...")
             texto = doc[0].get_text()
             if not texto:
                 logger.error(f"fitz tampoco pudo extraer texto de {pdf_path}")
                 return {"error": "No se pudo extraer texto del PDF con ninguna librería"}

        # Detectar el tipo de documento
        tipo_documento = detect_document_type(texto)
        
        # Procesar según el tipo de documento
        if tipo_documento == "ENDOSO_A":
            logger.info(f"Endoso tipo A detectado para {pdf_path}. Procediendo a extraer datos financieros.")
            datos_financieros = extraer_datos_endoso_a(pdf_path)
            if datos_financieros:
                logger.info(f"Datos financieros extraídos exitosamente para {pdf_path}.")
                return {
                    "tipo_documento": "ENDOSO_A",
                    "tipo_endoso": "A",
                    "descripcion": "MODIFICACIÓN DE DATOS",
                    "datos_financieros": datos_financieros
                }
            else:
                logger.error(f"Se detectó Endoso A para {pdf_path}, pero no se pudieron extraer los datos financieros.")
                return {"error": "Se detectó Endoso A, pero no se pudieron extraer los datos financieros"}
        
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
                    "tasa_financiamiento": "0"  # No aplica para pólizas de vida
                }
                
                return {
                    "tipo_documento": "POLIZA_VIDA",  # Usamos el mismo tipo para mantener compatibilidad con el frontend
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
                    "tasa_financiamiento": "0"  # No aplica para pólizas de vida
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
        
        else:
            logger.warning(f"Tipo de documento no soportado o desconocido para {pdf_path}")
            return {"error": "Tipo de documento no soportado o desconocido"}
            
    except Exception as e:
        # Capturar errores específicos
        logger.error(f"Error general al validar documento {pdf_path}: {str(e)}", exc_info=True)
        return {"error": f"Error interno al procesar el PDF: {str(e)}"}
    finally:
        if doc:
            doc.close()

if __name__ == "__main__":
    # Ejemplo de uso
    pdf_path = "ruta/al/documento.pdf"  # Reemplazar con la ruta real
    resultado = validate_endoso(pdf_path)
    print(resultado) 