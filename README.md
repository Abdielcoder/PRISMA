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
- Soporta múltiples tipos de documentos:
  - Endosos tipo A (modificación de datos)
  - Pólizas de vida

#### `endosos_autos_a.py` (anteriormente `extract_financial.py`)
- Módulo de extracción de datos financieros para endosos tipo A
- Funciones principales:
  - `extract_financial_data(pdf_path)`: Función principal que extrae datos financieros de un PDF
  - `extract_traditional_format(text)`: Extrae valores financieros del formato tradicional
  - `extract_modern_format(text)`: Extrae valores financieros del formato moderno
- Maneja diferentes formatos de pólizas y normaliza los datos extraídos

#### `data_ia_general_vida.py`
- Módulo para procesar pólizas de vida
- Funciones principales:
  - `procesar_archivo(ruta_pdf, directorio_salida)`: Procesa un PDF de póliza de vida
  - `extraer_datos_poliza_vida(pdf_path)`: Extrae datos específicos de pólizas de vida
  - `extraer_datos_desde_markdown(ruta_md)`: Extrae datos desde un archivo markdown estructurado
  - `generar_markdown(datos, ruta_salida)`: Genera un archivo markdown con los datos extraídos
- Extrae información detallada:
  - Datos del contratante y asegurado
  - Información financiera (Prima Neta, Prima anual total)
  - Fechas de emisión y vigencia
  - Información del agente
  - Detalles de la cobertura

#### `validar_tipo_endoso.py`
- Módulo para identificar y validar el tipo de documento
- Funciones principales:
  - `validate_endoso(pdf_path)`: Función principal que valida el tipo de documento
  - `detect_document_type(text)`: Detecta el tipo de documento basado en el contenido
  - `extract_text_from_pdf(pdf_path)`: Extrae texto del PDF para análisis
- Actualmente soporta:
  - Endosos tipo A (modificación de datos del asegurado)
  - Pólizas de vida

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
- `output/`: Carpeta para archivos de salida generados (JSON y Markdown)
- `loads/`: Carpeta para archivos temporales durante el procesamiento

## Uso

1. Para validar y procesar un documento:
   ```bash
   python validar_tipo_endoso.py ruta/al/documento.pdf
   ```

2. Para procesar una póliza individual (endoso tipo A):
   ```bash
   python endosos_autos_a.py ruta/al/archivo.pdf
   ```

3. Para procesar una póliza de vida:
   ```bash
   python data_ia_general_vida.py ruta/al/vida.pdf
   ```

4. Para procesar múltiples pólizas:
   ```bash
   python test_polizas.py
   ```

5. Para analizar la estructura de un PDF:
   ```bash
   python analyze_pdf.py
   ```

6. Para iniciar la aplicación web:
   ```bash
   python app.py
   ```

## Interfaz Web

La aplicación web permite:
- Cargar archivos PDF o procesarlos desde URL
- Detectar automáticamente el tipo de documento
- Visualizar la vista previa del documento
- Para endosos tipo A:
  - Mostrar datos financieros extraídos
  - Verificar automáticamente valores como prima neta, IVA, etc.
- Para pólizas de vida:
  - Mostrar todos los datos extraídos de la póliza
  - Visualizar información personal, fechas, valores financieros, etc.
  - Formatear automáticamente valores monetarios

## Flujo de Procesamiento de Pólizas de Vida

1. Se detecta el tipo de documento como póliza de vida
2. Se extraen los datos utilizando patrones específicos para este tipo de documento
3. Se genera un archivo Markdown estructurado con los datos extraídos
4. Se procesa el Markdown para extraer y normalizar los datos
5. Se genera un archivo JSON con todos los datos procesados
6. La interfaz web muestra todos los campos con sus valores formateados

## Dependencias

- Flask: Framework web
- PyMuPDF (fitz): Procesamiento de PDFs
- PyPDF2: Extracción de texto de PDFs
- Otros módulos estándar de Python

## Notas

- Los archivos de resultados se guardan en formato JSON
- Los datos de pólizas de vida también se almacenan en formato Markdown para fácil lectura
- Se incluyen logs detallados para facilitar el debugging
- La aplicación web permite una interfaz visual para el procesamiento de pólizas
- El sistema está preparado para expandirse a otros tipos de documentos en el futuro
