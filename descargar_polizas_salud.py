import json
import requests
import os
import urllib.parse
from pathlib import Path
import time

def crear_carpeta_si_no_existe(carpeta):
    """Crea una carpeta si no existe."""
    if not os.path.exists(carpeta):
        os.makedirs(carpeta)
        print(f"Carpeta '{carpeta}' creada correctamente.")
    else:
        print(f"La carpeta '{carpeta}' ya existe.")

def obtener_nombre_archivo(url):
    """Extrae el nombre del archivo desde la URL."""
    # Obtener el nombre del archivo de la URL
    nombre_archivo = os.path.basename(urllib.parse.urlparse(url).path)
    
    # Si no hay nombre de archivo en la URL, usar un nombre predeterminado con timestamp
    if not nombre_archivo:
        timestamp = int(time.time())
        nombre_archivo = f"poliza_salud_{timestamp}.pdf"
    
    return nombre_archivo

def descargar_archivo(url, carpeta_destino):
    """Descarga un archivo desde una URL y lo guarda en la carpeta de destino."""
    try:
        # Obtener el nombre del archivo
        nombre_archivo = obtener_nombre_archivo(url)
        ruta_destino = os.path.join(carpeta_destino, nombre_archivo)
        
        # Realizar la solicitud HTTP
        print(f"Descargando: {url}")
        respuesta = requests.get(url, stream=True, timeout=30)
        respuesta.raise_for_status()  # Verificar si hubo errores en la descarga
        
        # Guardar el archivo
        with open(ruta_destino, 'wb') as archivo:
            for chunk in respuesta.iter_content(chunk_size=8192):
                if chunk:
                    archivo.write(chunk)
        
        print(f"Archivo guardado como: {ruta_destino}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error al descargar {url}: {e}")
        return False

def main():
    # Configuración
    archivo_json = "salud.json"
    carpeta_destino = "polizas-salud"
    
    # Crear la carpeta de destino si no existe
    crear_carpeta_si_no_existe(carpeta_destino)
    
    # Leer el archivo JSON
    try:
        with open(archivo_json, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        
        # Verificar si hay datos y extraer las URIs
        if not datos:
            print(f"El archivo {archivo_json} está vacío o no contiene datos válidos.")
            return
        
        # Extraer las URIs del archivo JSON
        # Asumimos que las URIs pueden estar en diferentes formatos/estructuras en el JSON
        # Esta parte puede necesitar ajustes según la estructura real del archivo
        uris = []
        
        # Si datos es una lista
        if isinstance(datos, list):
            for item in datos:
                if isinstance(item, dict) and 'uri' in item:
                    uris.append(item['uri'])
                elif isinstance(item, str) and (item.startswith('http') or item.startswith('https')):
                    uris.append(item)
        
        # Si datos es un diccionario
        elif isinstance(datos, dict):
            # Buscar URIs en keys específicas como 'uris', 'links', 'urls', etc.
            for key in ['uris', 'urls', 'links', 'documentos']:
                if key in datos and isinstance(datos[key], list):
                    for item in datos[key]:
                        if isinstance(item, dict) and 'uri' in item:
                            uris.append(item['uri'])
                        elif isinstance(item, str) and (item.startswith('http') or item.startswith('https')):
                            uris.append(item)
            
            # Revisar todos los valores del diccionario
            for key, value in datos.items():
                if isinstance(value, str) and (value.startswith('http') or value.startswith('https')):
                    uris.append(value)
        
        # Si no se encontraron URIs en los formatos anteriores, intentar otras estrategias
        if not uris:
            print("No se encontraron URIs en el formato esperado. Intentando buscar en todo el JSON...")
            
            # Convertir todo el JSON a string y buscar patrones de URLs
            import re
            json_str = json.dumps(datos)
            # Patron para URLs que comienzan con http o https
            url_pattern = r'https?://[^\s,\'"]+\.(?:pdf|PDF)'
            uris = re.findall(url_pattern, json_str)
        
        # Descargar archivos
        if uris:
            print(f"Se encontraron {len(uris)} URIs para descargar.")
            exitos = 0
            for i, uri in enumerate(uris, 1):
                print(f"\nDescargando archivo {i} de {len(uris)}")
                if descargar_archivo(uri, carpeta_destino):
                    exitos += 1
                # Pequeña pausa entre descargas para no sobrecargar el servidor
                if i < len(uris):
                    time.sleep(1)
            
            print(f"\nProceso completado. Se descargaron {exitos} de {len(uris)} archivos.")
        else:
            print("No se encontraron URIs para descargar en el archivo JSON.")
    
    except json.JSONDecodeError:
        print(f"Error al decodificar {archivo_json}. Asegúrate de que es un archivo JSON válido.")
    except FileNotFoundError:
        print(f"No se encontró el archivo {archivo_json}. Verifica la ruta e intenta nuevamente.")
    except Exception as e:
        print(f"Error inesperado: {e}")

if __name__ == "__main__":
    main()
