# PRISMA - Procesamiento de Pólizas de Seguro

Este proyecto está diseñado para procesar y extraer información financiera de pólizas de seguro en formato PDF.

## Estructura del Proyecto

### Archivos Principales

#### `app.py`
- Archivo principal de la aplicación web
- Implementa un servidor Flask que maneja:
  - Carga de archivos PDF
  - Procesamiento de URLs de PDFs
  - Visualización de datos financieros
  - Interfaz web para la interacción con el usuario
- Incluye rutas para:
  - Página principal (`/`)
  - Carga de archivos (`/upload`)
  - Vista previa de PDFs (`/pdf_preview`)

#### `extract_financial.py`
- Módulo de extracción de datos financieros
- Funciones principales:
  - `extract_financial_data(pdf_path)`: Función principal que extrae datos financieros de un PDF
  - `extract_traditional_format(text)`: Extrae valores financieros del formato tradicional
  - `extract_modern_format(text)`: Extrae valores financieros del formato moderno
- Maneja diferentes formatos de pólizas y normaliza los datos extraídos

#### `test_polizas.py`
- Script de prueba para procesar múltiples pólizas
- Funcionalidades:
  - Procesa una lista predefinida de pólizas
  - Extrae datos financieros de cada póliza
  - Guarda los resultados en `resultados_polizas.json`
  - Muestra logs detallados del proceso

#### `analyze_pdf.py`
- Herramienta de análisis de estructura de PDFs
- Funciones:
  - `analyze_pdf_structure(pdf_path)`: Analiza la estructura de un PDF
  - Muestra el texto completo con números de línea
  - Busca y muestra coincidencias de términos financieros
  - Analiza patrones numéricos en el documento

### Carpetas

- `A/`, `B/`, `D/`: Carpetas para almacenar pólizas de diferentes tipos
- `output/`: Carpeta para archivos de salida generados
- `loads/`: Carpeta para archivos temporales durante el procesamiento

## Uso

1. Para procesar una póliza individual:
   ```bash
   python extract_financial.py ruta/al/archivo.pdf
   ```

2. Para procesar múltiples pólizas:
   ```bash
   python test_polizas.py
   ```

3. Para analizar la estructura de un PDF:
   ```bash
   python analyze_pdf.py
   ```

4. Para iniciar la aplicación web:
   ```bash
   python app.py
   ```

## Dependencias

- Flask: Framework web
- PyMuPDF (fitz): Procesamiento de PDFs
- Otros módulos estándar de Python

## Notas

- Los archivos de resultados se guardan en formato JSON
- Se incluyen logs detallados para facilitar el debugging
- La aplicación web permite una interfaz visual para el procesamiento de pólizas
