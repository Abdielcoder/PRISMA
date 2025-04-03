# Análisis de Extracción de Datos de Endosos de Seguros de Autos

## Resumen del Sistema Actual

El sistema actual está diseñado para extraer información financiera específica de archivos PDF de endosos de seguros de autos. La función principal es `extraer_datos_endoso_a()` dentro del archivo `endosos_autos_a.py`.

### Datos extraídos actualmente:
- Prima neta
- Gastos por expedición
- IVA
- Precio total
- Ramo (siempre "AUTOS")
- Tipo de endoso (siempre "A - MODIFICACIÓN DE DATOS")

### Estado actual
Actualmente, el extractor funciona correctamente para varios formatos, pero presenta problemas con algunos PDF específicos. De 22 archivos de prueba en la carpeta "A/", 8 no pueden ser procesados correctamente.

## Análisis de los Formatos de PDF

### Formatos identificados
Basado en la revisión de los PDFs, he identificado los siguientes formatos de presentación de datos financieros:

1. **Formato estándar**: Los valores aparecen directamente después de las etiquetas
   ```
   Prima neta       30.61
   Gastos por expedición    50.00
   I.V.A.           6.44
   Precio total     87.05
   ```

2. **Formato tabular**: Los valores aparecen en una tabla con columnas
   ```
   | Coberturas | Suma asegurada | Deducible | Prima |
   |------------|----------------|-----------|-------|
   | ... | ... | ... | ... |
   ```
   Seguido por un bloque como:
   ```
   Prima neta            83.19
   Tasa de financiamiento 0.00
   Gastos por expedición  50.00
   I.V.A.                10.65
   Precio total         143.84
   ```

3. **Formato línea-por-línea**: Los campos y valores están separados en líneas consecutivas
   ```
   Prima neta
   83.19
   Tasa de financiamiento
   0.00
   Gastos por expedición
   50.00
   I.V.A.
   10.65
   Precio total
   143.84
   ```

### Patrones de expresiones regulares

El sistema utiliza varios patrones de expresiones regulares para intentar extraer la información:

1. Para valores en línea:
   ```python
   r'Prima\s+neta\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
   ```

2. Para valores que pueden estar en la siguiente línea:
   ```python
   r'Prima\s+neta\s*\n\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
   ```

3. Para bloques de texto con etiquetas seguidas por valores:
   ```python
   r'Prima neta\s*\nTasa de financiamiento\s*\nGastos por expedición\s*\nI\.V\.A\.\s*\nPrecio total\s*\n'
   ```

## Archivos con Problemas de Extracción

Los siguientes archivos presentan dificultades para la extracción:

1. O_6731931_AUTOS_AUTOS-INDIVIDUAL_130259641604_A0550364_000001_16052024_000048_077293_646081_F_16052024_000000_1715817600_sinOT.pdf
2. O_8192372_AUTOS_AUTOS-INDIVIDUAL_130248841605_A0578501_000001_01032025_000048_077293_086096_F_01032025_000000_1740787200_sinOT.pdf
3. O_7360025_AUTOS_AUTOS-INDIVIDUAL_130209148705_A0563199_000001_14032024_000048_077293_646081_F_14032024_000000_1710374400_sinOT.pdf
4. O_7137397_AUTOS_AUTOS-INDIVIDUAL_130272450604_A0558654_000001_01092024_000048_077293_646081_F_01092024_000000_1725148800_sinOT.pdf
5. O_7135335_AUTOS_AUTOS-INDIVIDUAL_140282131802_A0558569_000001_01092024_000048_077293_646081_F_01092024_000000_1725148800_sinOT.pdf
6. O_8191647_AUTOS_AUTOS-INDIVIDUAL_160216163400_A0578482_000001_06032025_000048_077293_607356_F_06032025_000000_1741219200_sinOT.pdf
7. O_6604729_AUTOS_AUTOS-INDIVIDUAL_130235277504_A0547958_000001_17112023_000048_077293_646081_F_17112023_000000_1700179200_sinOT.pdf
8. O_6677204_AUTOS_AUTOS-INDIVIDUAL_140270130602_A0549301_000001_17052024_000048_077293_646081_F_17052024_000000_1715904000_sinOT.pdf

Del análisis del primer archivo (O_6731931), se puede observar que los datos financieros están presentes en el formato tabular, con los siguientes valores:

```
Prima neta                    83.19
Tasa de financiamiento        0.00
Gastos por expedición         50.00
I.V.A.                        10.65
Precio total                 143.84
```

## Sugerencias de Mejora

Para mejorar el sistema de extracción, se recomienda:

1. **Ampliar los patrones de expresiones regulares**:
   - Añadir patrones que manejen específicamente el formato donde las etiquetas y valores están alineados verticalmente
   - Mejorar los patrones para manejar espacios y formatos de números variables

2. **Implementar detección automática de formato**:
   - Crear una función que identifique automáticamente el formato del PDF
   - Aplicar diferentes estrategias de extracción según el formato detectado

3. **Mejorar el manejo de errores**:
   - Agregar más información de depuración para entender por qué fallan ciertas extracciones
   - Implementar un sistema de "fallback" que intente métodos alternativos cuando el principal falla

4. **Optimizar el proceso de extracción**:
   - Considerar el uso de herramientas adicionales como técnicas de OCR para PDFs más complejos
   - Implementar una estrategia de caché para evitar re-procesar PDFs ya analizados

## Conclusión

El sistema actual de extracción funciona para la mayoría de los PDFs pero requiere mejoras para manejar todos los formatos identificados. Con las mejoras sugeridas, debería ser posible aumentar significativamente la tasa de éxito en la extracción de datos. 