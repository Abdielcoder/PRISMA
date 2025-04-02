import fitz
import re

def extract_text_from_pdf(pdf_path):
    try:
        # Abrir el PDF
        doc = fitz.open(pdf_path)
        
        # Obtener el texto de la primera página
        text = doc[0].get_text()
        
        # Imprimir el texto completo
        print("=== TEXTO COMPLETO DEL PDF ===")
        print(text)
        print("\n=== BÚSQUEDA DE VALORES FINANCIEROS ===")
        
        # Buscar valores financieros con patrones más específicos
        patterns = {
            "Prima neta": [
                r"Prima neta[^\d]*([\d,.]+)",
                r"PRIMA NETA[^\d]*([\d,.]+)",
                r"Prima Neta[^\d]*([\d,.]+)"
            ],
            "Tasa de financiamiento": [
                r"Tasa de financiamiento[^\d]*([\d,.]+)",
                r"TASA DE FINANCIAMIENTO[^\d]*([\d,.]+)",
                r"Tasa Financiamiento[^\d]*([\d,.]+)"
            ],
            "Gastos por expedición": [
                r"Gastos por expedición[^\d]*([\d,.]+)",
                r"GASTOS POR EXPEDICIÓN[^\d]*([\d,.]+)",
                r"Gastos Expedición[^\d]*([\d,.]+)"
            ],
            "I.V.A.": [
                r"I\.V\.A\.[^\d]*([\d,.]+)",
                r"IVA[^\d]*([\d,.]+)",
                r"I\.V\.A[^\d]*([\d,.]+)"
            ],
            "Precio total": [
                r"Precio total[^\d]*([\d,.]+)",
                r"PRECIO TOTAL[^\d]*([\d,.]+)",
                r"Total[^\d]*([\d,.]+)",
                r"TOTAL[^\d]*([\d,.]+)"
            ]
        }
        
        # Buscar cada valor
        for key, pattern_list in patterns.items():
            print(f"\nBuscando {key}:")
            for pattern in pattern_list:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    print(f"- Patrón '{pattern}' encontró: {match.group(1)}")
        
        doc.close()
        
    except Exception as e:
        print(f"Error al procesar el PDF: {str(e)}")

# Procesar el primer PDF
pdf_path = "A/O_6604729_AUTOS_AUTOS-INDIVIDUAL_130235277504_A0547958_000001_17112023_000048_077293_646081_F_17112023_000000_1700179200_sinOT.pdf"
extract_text_from_pdf(pdf_path) 