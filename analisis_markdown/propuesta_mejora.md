# Propuesta de Mejora para el Extractor de Datos de PDFs de Endosos

## Resumen del Problema

El sistema actual extrae información financiera de PDFs de endosos de seguros de autos, pero tiene dificultades con ciertos formatos. De los 22 archivos de prueba, 8 no pueden ser procesados correctamente.

## Propuesta de Solución

### 1. Mejora de Expresiones Regulares

#### Patrones actualizados

Actualizar los patrones de expresiones regulares para manejar todos los formatos identificados:

```python
patrones_prima_neta = [
    # Formato estándar
    r'Prima\s+neta\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
    
    # Formato con nueva línea y espacios
    r'Prima\s+neta\s*\n\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
    
    # Formato con amplia alineación derecha
    r'Prima neta\s*\n\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2}))',
    
    # Captura más flexible con cualquier cantidad de espacios y saltos de línea
    r'Prima\s+neta[\s\n]*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
]
```

Aplicar el mismo enfoque para los otros valores (gastos, IVA, precio total).

### 2. Detección de Formato y Estrategia Adaptativa

Implementar un sistema que detecte automáticamente el formato del PDF y aplique la estrategia de extracción más adecuada:

```python
def detectar_formato(texto_pdf):
    """
    Detecta el formato del PDF basado en patrones específicos.
    Retorna un identificador de formato.
    """
    # Formato 1: Valores en línea
    if re.search(r'Prima\s+neta\s+\d', texto_pdf):
        return "FORMATO_LINEAL"
    
    # Formato 2/3: Etiquetas y valores en líneas separadas
    if re.search(r'Prima\s+neta\s*\n\s*\d', texto_pdf):
        return "FORMATO_VERTICAL"
    
    # Formato 4: Con tabla previa
    if re.search(r'Coberturas\s+amparadas.*Suma\s+asegurada.*Deducible.*Prima', texto_pdf):
        return "FORMATO_TABLA"
    
    return "FORMATO_DESCONOCIDO"
```

### 3. Enfoque Escalonado de Extracción

Implementar un enfoque escalonado que intente diferentes estrategias si la primera falla:

```python
def extraer_datos_financieros(texto_pdf):
    """
    Enfoque escalonado para extraer datos financieros.
    """
    # Paso 1: Detectar formato
    formato = detectar_formato(texto_pdf)
    
    # Paso 2: Intentar extracción basada en formato
    resultado = None
    if formato == "FORMATO_LINEAL":
        resultado = extraer_formato_lineal(texto_pdf)
    elif formato == "FORMATO_VERTICAL":
        resultado = extraer_formato_vertical(texto_pdf)
    elif formato == "FORMATO_TABLA":
        resultado = extraer_formato_tabla(texto_pdf)
    
    # Paso 3: Si falla, intentar enfoque genérico
    if not resultado or not all(resultado.values()):
        resultado = extraer_generico(texto_pdf)
    
    # Paso 4: Como último recurso, intentar pdftotext crudo
    if not resultado or not all(resultado.values()):
        texto_crudo = obtener_texto_crudo(pdf_path)
        resultado = extraer_desde_texto_crudo(texto_crudo)
    
    return resultado
```

### 4. Mejora en el Pre-procesamiento del Texto

Aplicar técnicas de pre-procesamiento para mejorar la calidad del texto extraído:

```python
def preprocesar_texto(texto):
    """
    Preprocesa el texto para mejorar la extracción.
    """
    # Normalizar espacios en blanco
    texto = re.sub(r'\s+', ' ', texto)
    
    # Normalizar saltos de línea
    texto = re.sub(r'(?<!\n)\n(?!\n)', ' ', texto)
    
    # Normalizar números (asegurar punto decimal)
    texto = re.sub(r'(\d),(\d)', r'\1.\2', texto)
    
    return texto
```

### 5. Log y Depuración Mejorados

Implementar un sistema de logging más detallado para facilitar la depuración y el análisis de errores:

```python
def extraer_con_log(pdf_path):
    """
    Extrae datos con logging detallado.
    """
    logging.info(f"Procesando archivo: {pdf_path}")
    
    try:
        texto = extraer_texto(pdf_path)
        
        logging.debug(f"Texto extraído (primeros 500 caracteres): {texto[:500]}")
        logging.debug(f"Formato detectado: {detectar_formato(texto)}")
        
        for campo, patrones in PATRONES.items():
            for i, patron in enumerate(patrones):
                match = re.search(patron, texto)
                if match:
                    valor = match.group(1)
                    logging.info(f"Encontrado {campo}: {valor} con patrón #{i+1}")
                    break
            else:
                logging.warning(f"No se encontró valor para {campo}")
        
        resultado = extraer_datos_financieros(texto)
        
        if resultado and all(resultado.values()):
            logging.info(f"Extracción exitosa: {resultado}")
            return resultado
        else:
            logging.error(f"Extracción incompleta: {resultado}")
            return None
            
    except Exception as e:
        logging.error(f"Error en la extracción: {str(e)}", exc_info=True)
        return None
```

### 6. Uso de Técnicas de OCR para Casos Difíciles

Para PDFs que son realmente problemáticos, implementar un sistema de respaldo que utilice OCR:

```python
def extraer_via_ocr(pdf_path):
    """
    Utiliza OCR para extraer texto de PDFs problemáticos.
    """
    try:
        import pytesseract
        from pdf2image import convert_from_path
        
        # Convertir PDF a imágenes
        images = convert_from_path(pdf_path, dpi=300)
        
        # Extraer texto de las imágenes
        texto_completo = ""
        for img in images:
            texto_completo += pytesseract.image_to_string(img, lang='spa')
        
        # Procesar el texto mediante el flujo normal
        return extraer_datos_financieros(texto_completo)
        
    except Exception as e:
        logging.error(f"Error en OCR: {str(e)}")
        return None
```

## Plan de Implementación

1. **Fase 1**: Actualizar los patrones de expresiones regulares y el pre-procesamiento de texto.
2. **Fase 2**: Implementar el sistema de detección de formato y el enfoque escalonado.
3. **Fase 3**: Mejorar el sistema de logging y depuración.
4. **Fase 4**: Integrar OCR como sistema de respaldo para casos difíciles.

## Ejemplos de Código Actualizado

```python
def extraer_datos_endoso_a(pdf_path):
    """
    Extrae los datos financieros de un PDF de tipo A.
    Versión mejorada con múltiples estrategias.
    """
    try:
        # Extraer texto del PDF
        reader = PdfReader(pdf_path)
        if len(reader.pages) < 1:
            logging.error(f"El PDF {pdf_path} no tiene páginas")
            return None
            
        # Extraer texto SOLO de la primera página
        texto_pdf = reader.pages[0].extract_text()
        
        # Detectar formato
        formato = detectar_formato(texto_pdf)
        logging.info(f"Formato detectado: {formato}")
        
        # Inicializar variables
        prima_neta = None
        gastos_expedicion = None
        iva = None
        precio_total = None
        
        # Intentar extracción según formato
        if formato == "FORMATO_LINEAL":
            # Patrones para valores en línea
            patrones = {
                'prima_neta': [r'Prima\s+neta\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'],
                'gastos_expedicion': [r'Gastos\s+por\s+expedición\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'],
                'iva': [r'I\.V\.A\.\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'],
                'precio_total': [r'Precio\s+total\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)']
            }
        elif formato == "FORMATO_VERTICAL":
            # Patrones para valores en líneas separadas
            patrones = {
                'prima_neta': [r'Prima\s+neta\s*\n\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'],
                'gastos_expedicion': [r'Gastos\s+por\s+expedición\s*\n\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'],
                'iva': [r'I\.V\.A\.\s*\n\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'],
                'precio_total': [r'Precio\s+total\s*\n\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)']
            }
        else:
            # Patrones genéricos (para formato desconocido)
            patrones = {
                'prima_neta': [
                    r'Prima\s+neta\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
                    r'Prima\s+neta\s*\n\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
                    r'Prima\s+neta[\s\n]*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
                ],
                'gastos_expedicion': [
                    r'Gastos\s+por\s+expedición\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
                    r'Gastos\s+por\s+expedición\s*\n\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
                    r'Gastos\s+por\s+expedición[\s\n]*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
                ],
                'iva': [
                    r'I\.V\.A\.\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
                    r'I\.V\.A\.\s*\n\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
                    r'I\.V\.A\.[\s\n]*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
                ],
                'precio_total': [
                    r'Precio\s+total\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
                    r'Precio\s+total\s*\n\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
                    r'Precio\s+total[\s\n]*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
                ]
            }
        
        # Buscar valores usando patrones
        for campo, lista_patrones in patrones.items():
            for patron in lista_patrones:
                match = re.search(patron, texto_pdf)
                if match:
                    valor = match.group(1).replace(',', '')
                    logging.info(f'Encontrado {campo}: {match.group(1)} usando patrón: {patron}')
                    if campo == 'prima_neta':
                        prima_neta = float(valor)
                    elif campo == 'gastos_expedicion':
                        gastos_expedicion = float(valor)
                    elif campo == 'iva':
                        iva = float(valor)
                    elif campo == 'precio_total':
                        precio_total = float(valor)
                    break  # Si encontramos un valor, pasamos al siguiente campo
        
        # Si no encontramos todos los valores, intentar enfoque de bloque
        if not all([prima_neta, gastos_expedicion, iva, precio_total]):
            logging.info("Intentando enfoque de bloque...")
            resultado = extraer_bloque_financiero(texto_pdf)
            if resultado:
                if not prima_neta and 'prima_neta' in resultado:
                    prima_neta = resultado['prima_neta']
                if not gastos_expedicion and 'gastos_expedicion' in resultado:
                    gastos_expedicion = resultado['gastos_expedicion']
                if not iva and 'iva' in resultado:
                    iva = resultado['iva']
                if not precio_total and 'precio_total' in resultado:
                    precio_total = resultado['precio_total']
        
        # Si aún faltan valores, intentar con texto crudo
        if not all([prima_neta, gastos_expedicion, iva, precio_total]):
            logging.info("Intentando con texto crudo...")
            try:
                import subprocess
                result = subprocess.run(['pdftotext', '-raw', pdf_path, '-'], capture_output=True, text=True)
                texto_crudo = result.stdout
                resultado = extraer_desde_texto_crudo(texto_crudo)
                if resultado:
                    if not prima_neta and 'prima_neta' in resultado:
                        prima_neta = resultado['prima_neta']
                    if not gastos_expedicion and 'gastos_expedicion' in resultado:
                        gastos_expedicion = resultado['gastos_expedicion']
                    if not iva and 'iva' in resultado:
                        iva = resultado['iva']
                    if not precio_total and 'precio_total' in resultado:
                        precio_total = resultado['precio_total']
            except Exception as e:
                logging.error(f"Error al extraer texto crudo: {str(e)}")
        
        # Verificar si encontramos todos los valores necesarios
        if not all([prima_neta, gastos_expedicion, iva, precio_total]):
            logging.error('No se encontraron todos los valores requeridos')
            return None
        
        return {
            'prima_neta': prima_neta,
            'gastos_expedicion': gastos_expedicion,
            'iva': iva,
            'precio_total': precio_total,
            'ramo': 'AUTOS',
            'tipo_endoso': 'A - MODIFICACIÓN DE DATOS'
        }
        
    except Exception as e:
        logging.error(f"Error al procesar el archivo {pdf_path}: {str(e)}")
        return None
```

## Beneficios Esperados

1. **Mayor tasa de éxito**: Se espera que el sistema pueda procesar correctamente al menos el 95% de los PDFs de endosos.
2. **Mejor mantenibilidad**: La estructura modular y el sistema mejorado de logging facilitarán el mantenimiento y la depuración.
3. **Flexibilidad**: El sistema podrá adaptarse a nuevos formatos de PDF que puedan surgir en el futuro.
4. **Precisión**: Mediante el enfoque escalonado, se garantiza una mayor precisión en la extracción de datos.

## Conclusión

La implementación de estas mejoras permitirá un sistema más robusto y adaptable para la extracción de datos de PDFs de endosos de seguros de autos, superando las limitaciones actuales y proporcionando una solución más completa y confiable. 