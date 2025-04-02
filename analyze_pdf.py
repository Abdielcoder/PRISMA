import fitz
import re

def analyze_pdf_structure(pdf_path):
    try:
        # Abrir el PDF
        doc = fitz.open(pdf_path)
        
        # Obtener el texto de la primera página
        text = doc[0].get_text()
        
        # Imprimir el texto completo con números de línea
        print("=== TEXTO COMPLETO DEL PDF (CON NÚMEROS DE LÍNEA) ===")
        for i, line in enumerate(text.split('\n'), 1):
            print(f"{i:03d}: {line}")
        
        print("\n=== ANÁLISIS DE ESTRUCTURA ===")
        
        # Buscar secciones específicas
        sections = [
            "Prima neta",
            "Tasa de financiamiento",
            "Gastos por expedición",
            "I.V.A.",
            "Precio total"
        ]
        
        for section in sections:
            print(f"\nBuscando '{section}':")
            # Buscar todas las ocurrencias
            matches = list(re.finditer(f"{section}.*", text, re.IGNORECASE | re.MULTILINE))
            if matches:
                for i, match in enumerate(matches, 1):
                    # Obtener el contexto (5 caracteres antes y después)
                    start = max(0, match.start() - 20)
                    end = min(len(text), match.end() + 20)
                    context = text[start:end]
                    print(f"  Coincidencia {i}:")
                    print(f"    Contexto: ...{context}...")
                    print(f"    Posición: {match.start()}-{match.end()}")
            else:
                print("  No se encontraron coincidencias")
        
        # Buscar patrones numéricos
        print("\n=== ANÁLISIS DE VALORES NUMÉRICOS ===")
        number_pattern = r"[\d,.]+(?=\s|$)"
        numbers = re.finditer(number_pattern, text)
        print("Valores numéricos encontrados:")
        for match in numbers:
            # Obtener el contexto
            start = max(0, match.start() - 20)
            end = min(len(text), match.end() + 20)
            context = text[start:end]
            print(f"  Valor: {match.group()}")
            print(f"  Contexto: ...{context}...")
            print()
        
        doc.close()
        
    except Exception as e:
        print(f"Error al analizar el PDF: {str(e)}")

# Analizar el primer PDF
pdf_path = "A/O_6604729_AUTOS_AUTOS-INDIVIDUAL_130235277504_A0547958_000001_17112023_000048_077293_646081_F_17112023_000000_1700179200_sinOT.pdf"
analyze_pdf_structure(pdf_path) 