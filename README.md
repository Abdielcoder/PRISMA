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

#### `endosos_autos_a.py` (anteriormente `extract_financial.py`)
- Módulo de extracción de datos financieros para endosos tipo A
- Funciones principales:
  - `extract_financial_data(pdf_path)`: Función principal que extrae datos financieros de un PDF
  - `extract_traditional_format(text)`: Extrae valores financieros del formato tradicional
  - `extract_modern_format(text)`: Extrae valores financieros del formato moderno
- Maneja diferentes formatos de pólizas y normaliza los datos extraídos

#### `validar_tipo_endoso.py`
- Módulo para identificar y validar el tipo de endoso
- Funciones principales:
  - `validate_endoso(pdf_path)`: Función principal que valida el tipo de endoso
  - `detect_endoso_type(text)`: Detecta el tipo de endoso basado en el contenido
  - `extract_text_from_pdf(pdf_path)`: Extrae texto del PDF para análisis
- Actualmente soporta:
  - Endosos tipo A (modificación de datos del asegurado)

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

1. Para validar y procesar un endoso:
   ```bash
   python validar_tipo_endoso.py ruta/al/endoso.pdf
   ```

2. Para procesar una póliza individual (endoso tipo A):
   ```bash
   python endosos_autos_a.py ruta/al/archivo.pdf
   ```

3. Para procesar múltiples pólizas:
   ```bash
   python test_polizas.py
   ```

4. Para analizar la estructura de un PDF:
   ```bash
   python analyze_pdf.py
   ```

5. Para iniciar la aplicación web:
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
- El sistema está preparado para expandirse a otros tipos de endosos en el futuro
