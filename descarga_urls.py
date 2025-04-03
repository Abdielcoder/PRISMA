import json
import os
import requests
import logging
from urllib.parse import urlparse
from pathlib import Path

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- Configuración ---
JSON_FILE_PATH = "URLS_VIDA.json"  # Cambiado para usar el archivo de pólizas de vida
OUTPUT_DIRECTORY = "Ordinario-Vida-1"  # Cambiado para guardar en la carpeta Ordinario-Vida-1
# --------------------

def download_pdf(url: str, output_path: str):
    """Descarga un archivo PDF desde una URL y lo guarda en la ruta especificada."""
    try:
        logger.info(f"Descargando: {url}")
        response = requests.get(url, stream=True, timeout=30) # Añadir timeout
        response.raise_for_status()  # Lanza excepción para errores HTTP (4xx o 5xx)
        
        # Asegurarse de que el directorio de salida existe
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        logger.info(f"Guardado en: {output_path}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Error de red al descargar {url}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error inesperado al descargar o guardar {url}: {e}")
        return False

def main():
    # Asegurar que el directorio principal de salida exista
    Path(OUTPUT_DIRECTORY).mkdir(parents=True, exist_ok=True)
    
    # Leer el archivo JSON
    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            urls_data = json.load(f)
    except FileNotFoundError:
        logger.error(f"Error: El archivo {JSON_FILE_PATH} no fue encontrado.")
        return
    except json.JSONDecodeError:
        logger.error(f"Error: El archivo {JSON_FILE_PATH} no contiene un JSON válido.")
        return
    except Exception as e:
        logger.error(f"Error inesperado al leer {JSON_FILE_PATH}: {e}")
        return
        
    if not isinstance(urls_data, list):
        logger.error(f"Error: El JSON en {JSON_FILE_PATH} no es una lista.")
        return
        
    logger.info(f"Se encontraron {len(urls_data)} URLs en {JSON_FILE_PATH}.")
    
    # Descargar cada PDF
    descargas_exitosas = 0
    descargas_fallidas = 0
    
    for item in urls_data:
        if not isinstance(item, dict) or 'uri' not in item:
            logger.warning(f"Item inválido en JSON (se esperaba un diccionario con 'uri'): {item}")
            descargas_fallidas += 1
            continue
            
        url = item['uri']
        
        # Extraer nombre de archivo de la URL
        try:
            parsed_url = urlparse(url)
            file_name = os.path.basename(parsed_url.path)
            if not file_name.lower().endswith('.pdf'):
                 # Intentar un nombre genérico si no parece un PDF válido
                 logger.warning(f"URL no parece terminar en .pdf: {url}. Usando nombre genérico.")
                 file_name = f"poliza_vida_{descargas_exitosas + descargas_fallidas + 1}.pdf"
                 # Opcional: podrías decidir saltar esta URL si quieres ser más estricto
                 # descargas_fallidas += 1
                 # continue 
        except Exception:
            logger.warning(f"No se pudo extraer nombre de archivo de la URL: {url}. Usando nombre genérico.")
            file_name = f"poliza_vida_{descargas_exitosas + descargas_fallidas + 1}.pdf"
            
        output_path = os.path.join(OUTPUT_DIRECTORY, file_name)
        
        if download_pdf(url, output_path):
            descargas_exitosas += 1
        else:
            descargas_fallidas += 1
            
    logger.info("--- Resumen de Descargas ---")
    logger.info(f"Exitosas: {descargas_exitosas}")
    logger.info(f"Fallidas:  {descargas_fallidas}")
    logger.info(f"Total:     {descargas_exitosas + descargas_fallidas}")
    logger.info(f"Archivos guardados en el directorio: {OUTPUT_DIRECTORY}")

if __name__ == "__main__":
    main() 