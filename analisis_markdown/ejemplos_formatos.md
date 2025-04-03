# Ejemplos de Formatos de PDFs de Endosos de Seguros

A continuación se presentan ejemplos de los diferentes formatos identificados en los PDFs de endosos de seguros de autos.

## Formato 1: Estándar (valores en línea)

Ejemplo de archivo: `O_6026484_AUTOS_AUTOS-INDIVIDUAL_140249101302_A0535612_000001_25012024_000048_077293_086096_F_25012024_000000_1706140800_sinOT.pdf`

```
Prima neta       30.61
Gastos por expedición    50.00
I.V.A.           6.44
Precio total     87.05
```

Este formato presenta los valores financieros directamente a la derecha de cada etiqueta, con espacios variables entre la etiqueta y el valor.

## Formato 2: Tabular con valores alineados

Ejemplo de archivo: `O_6731931_AUTOS_AUTOS-INDIVIDUAL_130259641604_A0550364_000001_16052024_000048_077293_646081_F_16052024_000000_1715817600_sinOT.pdf`

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

En este formato, las etiquetas están alineadas a la derecha y los valores aparecen en la línea siguiente, también alineados a la derecha. Hay un amplio espacio entre la etiqueta y el valor.

## Formato 3: Vertical con etiquetas y valores separados

Ejemplo de archivo: `O_8192372_AUTOS_AUTOS-INDIVIDUAL_130248841605_A0578501_000001_01032025_000048_077293_086096_F_01032025_000000_1740787200_sinOT.pdf`

```
                                                                                           Prima neta
                         144.96
                                                                                           Tasa de financiamiento
                         0.00
                                                                                           Gastos por expedición
                         50.00
                                                                                           I.V.A.
                         15.60
                                                                                           Precio total
                         210.56
```

Similar al formato 2, pero con diferentes valores y posiblemente diferentes espaciados.

## Formato 4: Con tabla de coberturas previa

Ejemplo de archivo: `O_7360025_AUTOS_AUTOS-INDIVIDUAL_130209148705_A0563199_000001_14032024_000048_077293_646081_F_14032024_000000_1710374400_sinOT.pdf`

```
 Coberturas
                Coberturas amparadas                               Suma asegurada                   Deducible                    Prima
Robo Total                                                          Valor Comercial                   10%                          XX.XX
Responsabilidad Civil por Daños a Terceros                           1,000,000.00                                                 XX.XX
...

                                                                                           Prima neta
                         53.36
                                                                                           Tasa de financiamiento
                         2.67
                                                                                           Gastos por expedición
                         50.00
                                                                                           I.V.A.
                         8.49
                                                                                           Precio total
                         114.52
```

Este formato incluye una tabla previa que detalla las coberturas y sus primas individuales, seguida por el resumen financiero en formato vertical.

## Patrones de Extracción Requeridos

Para extraer correctamente los datos de todos estos formatos, se requieren distintos patrones de expresiones regulares:

1. **Para el formato estándar (en línea)**:
   ```python
   r'Prima\s+neta\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
   ```

2. **Para formatos con etiqueta y valor en líneas separadas**:
   ```python
   r'Prima\s+neta\s*\n\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
   ```

3. **Para buscar secuencias de etiquetas y luego extraer valores**:
   ```python
   r'Prima neta\s*\nTasa de financiamiento\s*\nGastos por expedición\s*\nI\.V\.A\.\s*\nPrecio total\s*\n'
   ```
   Seguido por la extracción de números que siguen estas etiquetas.

4. **Para formatos con amplio espaciado y alineación derecha**:
   ```python
   r'Prima\s+neta\s*\n\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
   ```

## Desafíos de Extracción

Los principales desafíos de extracción son:

1. **Variabilidad en el espaciado**: Los espacios entre etiquetas y valores varían significativamente.
2. **Formato de los números**: Los valores pueden incluir comas como separadores de miles o no.
3. **Alineación del texto**: Las etiquetas y valores pueden estar alineados a la izquierda, derecha o centrados.
4. **Separación vertical**: En algunos formatos, la etiqueta y el valor están en líneas consecutivas.
5. **Texto intermedio**: Puede haber texto adicional entre las etiquetas y los valores. 