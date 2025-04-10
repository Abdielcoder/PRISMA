import json
import os
import requests
from urllib.parse import urlparse
import shutil
from datetime import datetime
import sys

def crear_carpeta_salud():
    """Crea la carpeta 'salud' si no existe"""
    if not os.path.exists("salud"):
        os.makedirs("salud")
        print("Carpeta 'salud' creada correctamente")
    else:
        print("La carpeta 'salud' ya existe")

def descargar_archivo(url, ruta_destino):
    """Descarga un archivo desde una URL"""
    try:
        print(f"Descargando: {url} -> {ruta_destino}")
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(ruta_destino, 'wb') as f:
            shutil.copyfileobj(response.raw, f)
        
        print(f"✓ Descargado con éxito: {ruta_destino}")
        return True
    except Exception as e:
        print(f"✗ Error al descargar {url}: {str(e)}")
        return False

def extraer_datos_salud():
    """Extrae datos del archivo salud.json"""
    try:
        if not os.path.exists("salud.json"):
            print("El archivo salud.json no existe en la ubicación actual.")
            print(f"Ubicación actual: {os.getcwd()}")
            print("Archivos en el directorio actual:")
            for archivo in os.listdir('.'):
                print(f"  - {archivo}")
            return None
            
        with open("salud.json", "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
        
        print(f"Archivo salud.json cargado. Estructura detectada: {type(datos).__name__}")
        if isinstance(datos, dict):
            print(f"Claves encontradas: {', '.join(datos.keys())}")
        elif isinstance(datos, list):
            print(f"Lista con {len(datos)} elementos")
            
        return datos
    except FileNotFoundError:
        print("El archivo salud.json no existe")
        return None
    except json.JSONDecodeError as e:
        print(f"El archivo salud.json tiene un formato incorrecto: {str(e)}")
        return None
    except Exception as e:
        print(f"Error inesperado al leer salud.json: {str(e)}")
        return None

def procesar_datos_salud(datos):
    """Procesa los datos y guarda los archivos en la carpeta salud"""
    if not datos:
        print("No hay datos para procesar.")
        return
    
    total_archivos = 0
    archivos_descargados = 0
    
    # Crear archivo de registro
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join("salud", f"extraccion_log_{timestamp}.txt")
    
    with open(log_file, "w", encoding="utf-8") as log:
        log.write(f"Extracción iniciada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        log.write(f"Tipo de datos: {type(datos).__name__}\n")
        
        # Si datos es una lista de elementos
        if isinstance(datos, list):
            print(f"Procesando lista con {len(datos)} elementos")
            for i, item in enumerate(datos):
                resultado = procesar_item(item, i, log)
                if resultado:
                    archivos_descargados += 1
                total_archivos += 1
        
        # Si datos es un diccionario
        elif isinstance(datos, dict):
            print("Procesando diccionario...")
            
            # Caso especial: si contiene una lista de URLs directamente
            if "urls" in datos and isinstance(datos["urls"], list):
                print(f"Encontrada lista de URLs bajo clave 'urls': {len(datos['urls'])} elementos")
                for i, url in enumerate(datos["urls"]):
                    if isinstance(url, str) and url.startswith("http"):
                        nombre = os.path.basename(urlparse(url).path)
                        if not nombre or nombre == "":
                            nombre = f"archivo_{i}.pdf"
                        ruta_destino = os.path.join("salud", nombre)
                        exito = descargar_archivo(url, ruta_destino)
                        
                        if exito:
                            log.write(f"Archivo descargado: {nombre} desde {url}\n")
                            archivos_descargados += 1
                        total_archivos += 1
            
            # Caso 1: diccionario con archivos como valores
            for key, item in datos.items():
                if isinstance(item, str):
                    # Es probablemente una URL o ruta de archivo
                    if item.startswith("http"):
                        print(f"Procesando URL: {key} -> {item}")
                        nombre_archivo = os.path.basename(urlparse(item).path)
                        if not nombre_archivo or nombre_archivo == "":
                            nombre_archivo = f"{key}.pdf"
                        ruta_destino = os.path.join("salud", nombre_archivo)
                        
                        exito = descargar_archivo(item, ruta_destino)
                        
                        if exito:
                            log.write(f"Archivo descargado: {nombre_archivo} desde {item}\n")
                            archivos_descargados += 1
                        total_archivos += 1
                    elif item.endswith(".pdf"):
                        print(f"Procesando archivo local: {key} -> {item}")
                        nombre_archivo = key if key.endswith(".pdf") else f"{key}.pdf"
                        ruta_destino = os.path.join("salud", nombre_archivo)
                        
                        # Copiar archivo local
                        try:
                            shutil.copy2(item, ruta_destino)
                            log.write(f"Archivo copiado: {nombre_archivo} desde {item}\n")
                            archivos_descargados += 1
                            print(f"✓ Copiado con éxito: {ruta_destino}")
                        except Exception as e:
                            log.write(f"Error al copiar {item}: {str(e)}\n")
                            print(f"✗ Error al copiar {item}: {str(e)}")
                        
                        total_archivos += 1
            
            # Caso 2: diccionario con estructura más compleja
            if "archivos" in datos:
                archivos = datos["archivos"]
                if isinstance(archivos, list):
                    print(f"Procesando lista de archivos: {len(archivos)} elementos")
                    for archivo in archivos:
                        if isinstance(archivo, dict) and "url" in archivo:
                            url = archivo["url"]
                            nombre = archivo.get("nombre", os.path.basename(urlparse(url).path))
                            if not nombre or nombre == "":
                                nombre = f"archivo_{total_archivos}.pdf"
                            
                            ruta_destino = os.path.join("salud", nombre)
                            exito = descargar_archivo(url, ruta_destino)
                            
                            if exito:
                                log.write(f"Archivo descargado: {nombre} desde {url}\n")
                                archivos_descargados += 1
                            total_archivos += 1
                else:
                    print(f"La clave 'archivos' no contiene una lista, sino: {type(archivos).__name__}")
            
            # También guardar el JSON original en la carpeta
            with open(os.path.join("salud", "datos_salud.json"), "w", encoding="utf-8") as f:
                json.dump(datos, f, indent=2, ensure_ascii=False)
                log.write("Archivo datos_salud.json guardado\n")
                print("✓ Archivo datos_salud.json guardado")
        
        # Buscar en cualquier estructura para URLs
        urls_encontradas = buscar_urls_recursivamente(datos)
        if urls_encontradas:
            print(f"Se encontraron {len(urls_encontradas)} URLs en la estructura completa")
            for i, url in enumerate(urls_encontradas):
                nombre = os.path.basename(urlparse(url).path)
                if not nombre or nombre == "":
                    nombre = f"encontrado_{i}.pdf"
                ruta_destino = os.path.join("salud", nombre)
                
                exito = descargar_archivo(url, ruta_destino)
                if exito:
                    log.write(f"URL encontrada descargada: {nombre} desde {url}\n")
                    archivos_descargados += 1
                total_archivos += 1
        
        log.write(f"\nExtracción finalizada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log.write(f"Total de archivos procesados: {total_archivos}\n")
        log.write(f"Archivos guardados correctamente: {archivos_descargados}\n")
    
    print(f"\nProceso completado. Se procesaron {total_archivos} archivos.")
    print(f"Se guardaron {archivos_descargados} archivos en la carpeta 'salud'.")
    print(f"Detalles guardados en {log_file}")

def buscar_urls_recursivamente(datos, ya_encontrados=None):
    """Busca recursivamente cualquier URL en la estructura de datos"""
    if ya_encontrados is None:
        ya_encontrados = set()
    
    if isinstance(datos, str):
        if datos.startswith("http") and datos not in ya_encontrados:
            ya_encontrados.add(datos)
    elif isinstance(datos, dict):
        for key, value in datos.items():
            buscar_urls_recursivamente(value, ya_encontrados)
    elif isinstance(datos, list):
        for item in datos:
            buscar_urls_recursivamente(item, ya_encontrados)
    
    return list(ya_encontrados)

def procesar_item(item, indice, log):
    """Procesa un elemento individual del JSON"""
    if isinstance(item, dict):
        # Si el elemento tiene una URL directa
        if "url" in item:
            url = item["url"]
            nombre = item.get("nombre", os.path.basename(urlparse(url).path))
            if not nombre or nombre == "":
                nombre = f"archivo_{indice}.pdf"
            
            ruta_destino = os.path.join("salud", nombre)
            exito = descargar_archivo(url, ruta_destino)
            
            if exito:
                log.write(f"Archivo descargado: {nombre} desde {url}\n")
                return True
        
        # Si el elemento tiene datos para guardar en un archivo
        elif "contenido" in item:
            nombre = item.get("nombre", f"contenido_{indice}.txt")
            ruta_destino = os.path.join("salud", nombre)
            
            try:
                with open(ruta_destino, "w", encoding="utf-8") as f:
                    f.write(str(item["contenido"]))
                log.write(f"Contenido guardado en: {nombre}\n")
                print(f"✓ Contenido guardado en: {nombre}")
                return True
            except Exception as e:
                log.write(f"Error al guardar contenido en {nombre}: {str(e)}\n")
                print(f"✗ Error al guardar contenido en {nombre}: {str(e)}")
                return False
    
    # Si el elemento es una cadena (podría ser una URL directa)
    elif isinstance(item, str) and item.startswith("http"):
        nombre = os.path.basename(urlparse(item).path)
        if not nombre or nombre == "":
            nombre = f"archivo_{indice}.pdf"
        
        ruta_destino = os.path.join("salud", nombre)
        exito = descargar_archivo(item, ruta_destino)
        
        if exito:
            log.write(f"Archivo descargado: {nombre} desde {item}\n")
            return True
    
    return False

def mostrar_contenido_salud_json():
    """Muestra las primeras líneas del archivo salud.json para diagnóstico"""
    try:
        with open("salud.json", "r", encoding="utf-8") as f:
            contenido = f.read(1000)  # Leer primeros 1000 caracteres
        
        print("\nPrimeras líneas de salud.json:")
        print("-" * 40)
        print(contenido)
        print("-" * 40)
        print("(Mostrando primeros 1000 caracteres)")
    except Exception as e:
        print(f"Error al leer salud.json para diagnóstico: {str(e)}")

def main():
    """Función principal"""
    print("=" * 50)
    print("INICIANDO EXTRACCIÓN DE DATOS DE SALUD.JSON")
    print("=" * 50)
    print(f"Directorio actual: {os.getcwd()}")
    
    # Mostrar contenido del archivo salud.json para diagnóstico
    mostrar_contenido_salud_json()
    
    # Paso 1: Crear carpeta salud
    crear_carpeta_salud()
    
    # Paso 2: Extraer datos
    datos = extraer_datos_salud()
    
    if datos is None:
        print("\n⚠️ No se pudo cargar el archivo salud.json. Verificar que exista y tenga formato JSON válido.")
        sys.exit(1)
    
    # Paso 3: Procesar datos
    procesar_datos_salud(datos)

if __name__ == "__main__":
    main() 