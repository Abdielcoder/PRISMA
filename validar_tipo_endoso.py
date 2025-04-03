import fitz
import re
import logging
from typing import Dict, Optional
from endosos_autos_a import extraer_datos_endoso_a

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

def detect_endoso_type(text: str) -> Optional[str]:
    """
    Detecta el tipo de endoso basado en el contenido del texto.
    
    Args:
        text (str): Texto extraído del PDF
        
    Returns:
        Optional[str]: Tipo de endoso detectado o None si no se puede determinar
    """
    # Normalizar el texto
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    
    # Patrones para identificar endoso tipo A
    patterns = [
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
    
    # Buscar patrones en el texto
    for pattern in patterns:
        if re.search(pattern, text):
            logger.info(f"Detectado endoso tipo A con patrón: {pattern}")
            return "A"
    
    # Si no se encuentra ningún patrón, asumimos que es tipo A por defecto
    # ya que mencionaste que todos son de tipo A
    logger.info("No se encontró patrón específico, asumiendo endoso tipo A por defecto")
    return "A"

def validate_endoso(pdf_path: str) -> Dict:
    """
    Valida el tipo de endoso y extrae los datos financieros si corresponde.
    
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
            
        # Obtener el texto de la primera página
        # Usar fitz para extraer texto también, puede ser más robusto que PyPDF2 en algunos casos
        # texto = doc[0].get_text()
        # Intentemos extraer con PyPDF2 primero como lo hace extraer_datos_endoso_a
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(pdf_path)
            if len(reader.pages) > 0:
                 texto = reader.pages[0].extract_text() # Texto extraído por PyPDF2
            else:
                 texto = "" # O manejar error si prefieres
        except Exception as e_pypdf:
             logger.warning(f"PyPDF2 no pudo extraer texto de {pdf_path}: {e_pypdf}")
             # Fallback a fitz si PyPDF2 falla?
             logger.info(f"Intentando extraer texto con fitz para {pdf_path}...")
             texto = doc[0].get_text()
             if not texto:
                 logger.error(f"fitz tampoco pudo extraer texto de {pdf_path}")
                 return {"error": "No se pudo extraer texto del PDF con ninguna librería"}

        # Buscar el tipo de endoso usando la función robusta
        tipo_endoso = detect_endoso_type(texto)
        
        if not tipo_endoso:
            # Si detect_endoso_type no pudo determinarlo (aunque actualmente siempre devuelve 'A')
            logger.error(f"No se pudo determinar el tipo de endoso para {pdf_path}")
            return {"error": "No se pudo determinar el tipo de endoso con los patrones disponibles"}
            
        # Si es tipo A, extraer datos financieros
        if tipo_endoso == 'A':
            logger.info(f"Endoso tipo A detectado para {pdf_path}. Procediendo a extraer datos financieros.")
            # Pasamos el path, ya que extraer_datos_endoso_a maneja la extracción de texto internamente
            datos_financieros = extraer_datos_endoso_a(pdf_path)
            if datos_financieros:
                logger.info(f"Datos financieros extraídos exitosamente para {pdf_path}.")
                return {
                    "tipo_endoso": "A",
                    "descripcion": "MODIFICACIÓN DE DATOS", # Asumido para tipo A
                    "datos_financieros": datos_financieros
                }
            else:
                logger.error(f"Se detectó Endoso A para {pdf_path}, pero no se pudieron extraer los datos financieros.")
                return {"error": "Se detectó Endoso A, pero no se pudieron extraer los datos financieros"}
        else:
            logger.warning(f"Tipo de endoso no soportado actualmente: {tipo_endoso} en {pdf_path}")
            return {"error": f"Tipo de endoso no soportado actualmente: {tipo_endoso}"}
            
    except Exception as e:
        # Capturar errores específicos de fitz si es posible, o generales
        logger.error(f"Error general al validar endoso {pdf_path}: {str(e)}", exc_info=True)
        return {"error": f"Error interno al procesar el PDF: {str(e)}"}
    finally:
        if doc:
            doc.close()

if __name__ == "__main__":
    # Ejemplo de uso
    pdf_path = "ruta/al/endoso.pdf"  # Reemplazar con la ruta real
    resultado = validate_endoso(pdf_path)
    print(resultado) 