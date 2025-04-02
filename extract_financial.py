import os
import sys
import re
import json
import logging
import argparse
import fitz  # PyMuPDF
from datetime import datetime
import glob
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def normalizar_numero(valor):
    """Normaliza un número, eliminando caracteres no numéricos excepto punto y coma."""
    if not valor:
        return ""
    
    # Eliminar cualquier caracter que no sea dígito, punto o coma
    valor_limpio = re.sub(r'[^\d.,]', '', str(valor))
    
    # Si hay comas, reemplazarlas por puntos si es un separador decimal
    if ',' in valor_limpio and '.' not in valor_limpio:
        # Si la coma está a 2 o 3 posiciones del final, es un separador decimal
        if re.match(r'.*,\d{1,3}$', valor_limpio):
            valor_limpio = valor_limpio.replace(',', '.')
    
    # Si hay tanto comas como puntos, asumir que la coma es separador de miles
    if ',' in valor_limpio and '.' in valor_limpio:
        valor_limpio = valor_limpio.replace(',', '')
    
    # Si es solo una coma (sin puntos), podría ser un separador decimal
    if valor_limpio.count(',') == 1 and '.' not in valor_limpio:
        valor_limpio = valor_limpio.replace(',', '.')
    
    try:
        # Intentar convertir a float para validar
        float(valor_limpio)
        return valor_limpio
    except ValueError:
        # Si no se puede convertir, devolver el valor original
        return valor_limpio

def extract_financial_data(pdf_path):
    """Extrae los datos financieros de un PDF de póliza."""
    try:
        logging.info(f"Procesando archivo: {pdf_path}")
        doc = fitz.open(pdf_path)
        
        # Procesar primera página
        logging.info("Procesando primera página del PDF")
        text = doc[0].get_text()
        
        # Intentar determinar el formato del documento
        if "Carátula de endoso B" in text:
            logging.info("Detectado formato de endoso tipo B")
            return extract_endoso_b_data(text, pdf_path)
        elif "Prima neta" in text or "PRIMA NETA" in text:
            logging.info("Detectado formato tradicional (columna de datos)")
            return extract_traditional_format(text)
        else:
            logging.info("No se pudo determinar el formato del documento, usando análisis genérico")
            return extract_generic_format(text)
    except Exception as e:
        logging.error(f"Error al procesar el archivo {pdf_path}: {str(e)}")
        return {}

def extract_endoso_b_data(text, pdf_path):
    """Extrae datos específicos para endosos tipo B."""
    data = {}
    
    # Extraer número de póliza
    poliza_match = re.search(r'Póliza\s+(\d+)', text)
    if poliza_match:
        data["Número de póliza"] = poliza_match.group(1)
    
    # Extraer número de endoso
    endoso_match = re.search(r'Endoso\s+([A-Z0-9]+)', text)
    if endoso_match:
        data["Número de endoso"] = endoso_match.group(1)
    
    # Extraer vigencia
    vigencia_desde = re.search(r'Desde:\s+(\d{2}/\w{3}/\d{4})', text)
    vigencia_hasta = re.search(r'Hasta:\s+(\d{2}/\w{3}/\d{4})', text)
    if vigencia_desde:
        data["Vigencia desde"] = vigencia_desde.group(1)
    if vigencia_hasta:
        data["Vigencia hasta"] = vigencia_hasta.group(1)
    
    # Extraer datos del asegurado
    nombre_match = re.search(r'Nombre:\s+(.*?)(?:\s{3}|$)', text, re.DOTALL)
    if nombre_match:
        data["Nombre del asegurado"] = nombre_match.group(1).strip()
    
    # Extraer datos del vehículo
    vehiculo_match = re.search(r'Vehículo:\s+(.*?)(?:\s+Motor:|$)', text, re.DOTALL)
    if vehiculo_match:
        data["Vehículo"] = vehiculo_match.group(1).strip()
    
    # Extraer placa
    placa_match = re.search(r'Placas:\s+([A-Z0-9]+)', text)
    if placa_match:
        data["Placas"] = placa_match.group(1)
    
    # Extraer modelo
    modelo_match = re.search(r'Modelo:\s+(\d{4})', text)
    if modelo_match:
        data["Modelo"] = modelo_match.group(1)
    
    # Tipo de endoso (extraer de la descripción o del nombre del archivo)
    filename = os.path.basename(pdf_path)
    # Intentar extraer el tipo de endoso del nombre del archivo (ej: CAMBIO, CANCELACION)
    tipo_endoso_match = re.search(r'AUTOS/([A-Z]+)/', filename)
    if tipo_endoso_match:
        data["Tipo de endoso"] = tipo_endoso_match.group(1)
    
    # Extraer descripción del cambio
    descripcion_match = re.search(r'Se hace constar que, (.*?)(?:$|\n\n)', text, re.DOTALL)
    if descripcion_match:
        data["Descripción del cambio"] = descripcion_match.group(1).strip()
    
    # Si no hay datos financieros, indicar el motivo
    data["Nota"] = "Este es un endoso tipo B que no contiene información financiera"
    
    return data

def extract_traditional_format(text):
    """Extrae datos financieros del formato tradicional (columna de datos)"""
    logging.info("Detectado formato tradicional (columna de datos)")
    
    # Buscar el bloque de prima que contiene los valores financieros
    prima_pattern = r"Prima neta\s*([\d,]+\.?\d*)\s*Tasa de financiamiento\s*([\d,]+\.?\d*)\s*Gastos por expedición\s*([\d,]+\.?\d*)\s*I\.V\.A\.\s*([\d,]+\.?\d*)\s*Precio total\s*([\d,]+\.?\d*)"
    prima_match = re.search(prima_pattern, text, re.DOTALL)
    
    if prima_match:
        logging.info("Encontrado bloque de prima en formato tradicional")
        prima_neta = prima_match.group(1).replace(',', '')
        tasa_financiamiento = prima_match.group(2).replace(',', '')
        gastos_expedicion = prima_match.group(3).replace(',', '')
        iva = prima_match.group(4).replace(',', '')
        precio_total = prima_match.group(5).replace(',', '')
        
        logging.info(f"Valores encontrados: Prima neta={prima_neta}, Tasa={tasa_financiamiento}, "
                   f"Gastos={gastos_expedicion}, IVA={iva}, Total={precio_total}")
        
        return {
            "Prima neta": prima_neta,
            "Tasa de financiamiento": tasa_financiamiento,
            "Gastos por expedición": gastos_expedicion,
            "I.V.A.": iva,
            "Precio total": precio_total
        }
    
    # Si no se encuentra el bloque completo, intentar extraer valores individuales
    logging.info("No se encontró el bloque de prima en formato tradicional, intentando extraer valores individuales")
    
    # Patrones individuales para cada valor
    patterns = {
        "Prima neta": r"Prima neta\s*([\d,]+\.?\d*)",
        "Tasa de financiamiento": r"Tasa de financiamiento\s*([\d,]+\.?\d*)",
        "Gastos por expedición": r"Gastos por expedición\s*([\d,]+\.?\d*)",
        "I.V.A.": r"I\.V\.A\.\s*([\d,]+\.?\d*)",
        "Precio total": r"Precio total\s*([\d,]+\.?\d*)"
    }
    
    result = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            value = match.group(1).replace(',', '')
            result[key] = value
            logging.info(f"Encontrado {key}: {value}")
        else:
            logging.warning(f"No se encontró {key}")
    
    return result if result else None

def extract_generic_format(text):
    """Intenta extraer datos financieros usando patrones genéricos."""
    data = {}
    
    # Intentar extraer valores usando patrones más flexibles
    prima_neta_match = re.search(r'(?:Prima|PRIMA)[^\d]+([\d,.]+)', text)
    if prima_neta_match:
        data["Prima neta"] = normalizar_numero(prima_neta_match.group(1))
    
    tasa_match = re.search(r'(?:Tasa|TASA)[^\d]+([\d,.]+)', text)
    if tasa_match:
        data["Tasa de financiamiento"] = normalizar_numero(tasa_match.group(1))
    
    gastos_match = re.search(r'(?:Gastos|GASTOS)[^\d]+([\d,.]+)', text)
    if gastos_match:
        data["Gastos por expedición"] = normalizar_numero(gastos_match.group(1))
    
    iva_match = re.search(r'(?:I\.V\.A\.|IVA)[^\d]+([\d,.]+)', text)
    if iva_match:
        data["I.V.A."] = normalizar_numero(iva_match.group(1))
    
    precio_match = re.search(r'(?:Precio|PRECIO|Total|TOTAL)[^\d]+([\d,.]+)', text)
    if precio_match:
        data["Precio total"] = normalizar_numero(precio_match.group(1))
    
    return data

def save_to_json(data, output_path):
    """Guarda los datos en formato JSON."""
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info(f"Datos guardados en: {output_path}")
        return True
    except Exception as e:
        logging.error(f"Error al guardar el archivo JSON {output_path}: {str(e)}")
        return False

def create_markdown_table(data, output_path):
    """Crea una tabla en formato Markdown con los datos financieros."""
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Crear encabezado de la tabla
        table = "| Campo | Valor |\n"
        table += "|-------|-------|\n"
        
        # Añadir filas con los datos
        for key, value in data.items():
            table += f"| {key} | {value} |\n"
        
        # Guardar la tabla en un archivo
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(table)
        
        logging.info(f"Tabla de datos financieros añadida al final del archivo")
        return True
    except Exception as e:
        logging.error(f"Error al crear tabla Markdown {output_path}: {str(e)}")
        return False

def create_summary(results, output_md="resumen_financiero.md", output_json="resumen_financiero.json"):
    """Crea un archivo de resumen con todos los resultados."""
    try:
        # Crear tabla de resumen en Markdown
        with open(output_md, 'w', encoding='utf-8') as f:
            f.write("# Resumen Financiero de Pólizas\n\n")
            
            # Encabezado de la tabla
            headers = ["Póliza"]
            if results:
                first_result = next(iter(results.values()))
                headers.extend(first_result.keys())
            
            f.write("| " + " | ".join(headers) + " |\n")
            f.write("|" + "---|" * len(headers) + "\n")
            
            # Filas con datos
            for pdf_name, data in results.items():
                row = [pdf_name]
                for header in headers[1:]:
                    row.append(data.get(header, ""))
                f.write("| " + " | ".join(str(cell) for cell in row) + " |\n")
        
        # Guardar también en formato JSON
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logging.info(f"Resumen creado en: {output_md}")
        logging.info(f"Resumen guardado en: {output_json}")
        return True
    except Exception as e:
        logging.error(f"Error al crear el resumen: {str(e)}")
        return False

def process_single_file(pdf_path, base_output_dir="output"):
    """Procesa un único archivo PDF."""
    # Extraer los datos financieros
    data = extract_financial_data(pdf_path)
    
    # Crear nombre de archivo de salida
    basename = os.path.basename(pdf_path)
    output_json = os.path.join(base_output_dir, f"{basename.split('.')[0]}.json")
    output_md = os.path.join(base_output_dir, f"{basename.split('.')[0]}.md")
    
    # Guardar los datos extraídos
    save_to_json(data, output_json)
    create_markdown_table(data, output_md)
    
    return data

def process_directory(directory, base_output_dir="output"):
    """Procesa todos los PDFs en un directorio."""
    results = {}
    
    # Buscar todos los archivos PDF en el directorio
    pdf_files = glob.glob(os.path.join(directory, "*.pdf"))
    logging.info(f"Encontrados {len(pdf_files)} archivos PDF en el directorio {directory}")
    
    for pdf_file in pdf_files:
        logging.info(f"Procesando {pdf_file}...")
        data = process_single_file(pdf_file, base_output_dir)
        results[os.path.basename(pdf_file)] = data
    
    # Crear resumen
    create_summary(results)
    
    return results

def main():
    parser = argparse.ArgumentParser(description='Extrae datos financieros de PDFs de pólizas.')
    parser.add_argument('input', help='Ruta al archivo PDF o directorio con PDFs')
    parser.add_argument('--dir', action='store_true', help='Indica que la entrada es un directorio')
    parser.add_argument('--output', default='output', help='Directorio de salida')
    parser.add_argument('--json', action='store_true', help='Guardar resultados en formato JSON')
    
    args = parser.parse_args()
    
    # Crear directorio de salida si no existe
    os.makedirs(args.output, exist_ok=True)
    
    if args.dir:
        # Procesar todos los PDFs en el directorio
        process_directory(args.input, args.output)
    else:
        # Lista para almacenar múltiples archivos si se proporcionan
        pdf_files = []
        
        # Comprobar si es un patrón glob
        if '*' in args.input:
            pdf_files = glob.glob(args.input)
        else:
            # Comprobar si es un directorio (aunque no se haya especificado --dir)
            if os.path.isdir(args.input):
                logging.warning(f"{args.input} es un directorio. Considerando usar --dir para procesar todos los PDFs.")
                pdf_files = [args.input]
            else:
                # Tratar como una lista de archivos separados por espacios
                pdf_files = args.input.split()
        
        # Procesar cada archivo
        results = {}
        for pdf_file in pdf_files:
            data = process_single_file(pdf_file, args.output)
            results[os.path.basename(pdf_file)] = data
        
        # Crear resumen si hay más de un archivo
        if len(pdf_files) > 1:
            create_summary(results)
    
    logging.info("Proceso completado")

if __name__ == "__main__":
    main()