import os
import json
import logging
from endosos_autos_a import extraer_datos_endoso_a

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def test_endosos():
    """Prueba la extracción de datos de endosos tipo A."""
    # Directorio con los PDFs de prueba
    test_dir = "A"
    
    # Lista para almacenar los resultados
    resultados = []
    
    # Procesar cada PDF en el directorio
    for filename in os.listdir(test_dir):
        if filename.endswith('.pdf'):
            pdf_path = os.path.join(test_dir, filename)
            logging.info(f"\nProcesando: {filename}")
            logging.info("-" * 80)
            
            # Extraer datos del PDF
            datos = extraer_datos_endoso_a(pdf_path)
            
            if datos:
                # Formatear los datos para mejor legibilidad
                datos_formateados = {
                    'archivo': filename,
                    'precio_total': f"${datos['precio_total']:.2f}",
                    'ramo': datos['ramo'],
                    'tipo_endoso': datos['tipo_endoso']
                }
                
                # Imprimir los datos extraídos
                print("Datos extraídos:")
                for key, value in datos_formateados.items():
                    print(f"{key}: {value}")
                
                # Agregar a la lista de resultados
                resultados.append(datos_formateados)
            else:
                logging.error(f"No se pudieron extraer datos del archivo {filename}")
    
    # Guardar resultados en un archivo JSON
    with open('resultados_endosos.json', 'w', encoding='utf-8') as f:
        json.dump(resultados, f, ensure_ascii=False, indent=4)
    
    logging.info("Resultados guardados en resultados_endosos.json")

if __name__ == "__main__":
    test_endosos() 