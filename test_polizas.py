from extract_financial import extract_financial_data
import os
import json

# Lista de pólizas a procesar
polizas = [
    "O_6604729_AUTOS_AUTOS-INDIVIDUAL_130235277504_A0547958_000001_17112023_000048_077293_646081_F_17112023_000000_1700179200_sinOT.pdf",
    "O_6677204_AUTOS_AUTOS-INDIVIDUAL_140270130602_A0549301_000001_17052024_000048_077293_646081_F_17052024_000000_1715904000_sinOT.pdf",
    "O_6731931_AUTOS_AUTOS-INDIVIDUAL_130259641604_A0550364_000001_16052024_000048_077293_646081_F_16052024_000000_1715817600_sinOT.pdf",
    "O_7135335_AUTOS_AUTOS-INDIVIDUAL_140282131802_A0558569_000001_01092024_000048_077293_646081_F_01092024_000000_1725148800_sinOT.pdf",
    "O_7137397_AUTOS_AUTOS-INDIVIDUAL_130272450604_A0558654_000001_01092024_000048_077293_646081_F_01092024_000000_1725148800_sinOT.pdf",
    "O_7360025_AUTOS_AUTOS-INDIVIDUAL_130209148705_A0563199_000001_14032024_000048_077293_646081_F_14032024_000000_1710374400_sinOT.pdf",
    "O_8191647_AUTOS_AUTOS-INDIVIDUAL_160216163400_A0578482_000001_06032025_000048_077293_607356_F_06032025_000000_1741219200_sinOT.pdf",
    "O_8192372_AUTOS_AUTOS-INDIVIDUAL_130248841605_A0578501_000001_01032025_000048_077293_086096_F_01032025_000000_1740787200_sinOT.pdf"
]

def test_polizas():
    resultados = {}
    
    for poliza in polizas:
        ruta_completa = os.path.join('A', poliza)
        print(f"\nProcesando: {poliza}")
        print("-" * 80)
        
        try:
            datos = extract_financial_data(ruta_completa)
            resultados[poliza] = datos
            
            # Mostrar los datos extraídos
            print("Datos extraídos:")
            for key, value in datos.items():
                print(f"{key}: {value}")
                
        except Exception as e:
            print(f"Error al procesar {poliza}: {str(e)}")
    
    # Guardar resultados en un archivo JSON
    with open('resultados_polizas.json', 'w', encoding='utf-8') as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    
    return resultados

if __name__ == "__main__":
    resultados = test_polizas() 