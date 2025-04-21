import fitz
import re
import logging
import os
import json
import time
import shutil
import glob
from typing import Dict, Optional
from endosos_autos_a import extraer_datos_endoso_a
from data_ia_general_vida import procesar_archivo
from data_ia_general_vida_individual import procesar_archivo as procesar_archivo_individual
from data_ia_general_protgt_ordinario import procesar_archivo as procesar_archivo_protgt_ordinario
from data_ia_general_protgt_ppr import procesar_archivo as procesar_archivo_aliados_ppr
from data_ia_general_protgt_mn import procesar_archivo as procesar_archivo_protgt_temporal_mn
from data_ia_general_vida_protgt import procesar_archivo as procesar_archivo_vida_protgt
from data_ia_general_proteccion_efectiva import procesar_archivo as procesar_archivo_proteccion_efectiva
from data_ia_general_protgt_pyme import procesar_archivo as procesar_archivo_protgt_pyme
from data_ia_general_salud_familiar_variantef import procesar_archivo as procesar_archivo_salud_familiar_variantef
from data_ia_general_salud_familiar import procesar_archivo as procesar_archivo_salud_familiar
from datetime import datetime

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extrae el texto de un archivo PDF.
    
    Args:
        pdf_path (str): Ruta al archivo PDF
        
    Returns:
        str: Texto extraído del PDF
    """
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        logger.error(f"Error al extraer texto del PDF: {str(e)}")
        return ""

def detect_document_type(text: str) -> str:
    """
    Detecta el tipo de documento basado en el contenido del texto.
    
    Args:
        text (str): Texto extraído del PDF
        
    Returns:
        str: Tipo de documento detectado ('ENDOSO_A', 'POLIZA_VIDA', 'POLIZA_VIDA_INDIVIDUAL', 
                                         'PROTEGETE_ORDINARIO', 'ALIADOS_PPR', 'PROTGT_TEMPORAL_MN', 
                                         'VIDA_PROTGT', 'PROTECCION_EFECTIVA', 'PROTGT_PYME', 'DESCONOCIDO')
    """
    # Normalizar el texto
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    
    # Patrones para identificar Aliados+ PPR (MÁXIMA PRIORIDAD)
    patrones_aliados_ppr = [
        r"aliados\s*\+\s*ppr",
        r"aliados\s*\+",
        r"vida y ahorro",
        r"carátula de póliza.*aliados",
        r"aliados\+.*car[áa]tula",
        r"aliados.*ppr",
        r"póliza.*ahorro",
        r"vida.*ahorro",
        r"seguro.*ahorro",
        r"aliados\s*mas",
        r"ahorro.*programado",
        r"seguro.*aliados"
    ]
    
    # Patrones para identificar VIDA PROTGT
    patrones_vida_protgt = [
        r"vida protgt",
        r"protgt cobertura",
        r"cobertura conyugal",
        r"caratula de p[óo]liza.*vida\s*protgt",
        r"p[óo]liza.*vida\s*protgt"
    ]
    
    # Patrones para identificar Gastos Médicos Mayores Familiar
    patrones_salud_familiar = [
        r"gastos m[ée]dicos mayores individual",
        r"gastos m[ée]dicos mayores.*familiar",
        r"car[áa]tula de p[óo]liza.*gastos m[ée]dicos",
        r"tabulador médico",
        r"gama hospitalaria",
        r"coaseguro",
        r"flex plus"
    ]
    
    # Patrones para identificar Protegete Temporal MN
    patrones_protgt_temporal_mn = [
        r"vida protgt temporal mn",
        r"protgt temporal mn",
        r"temporal mn",
        r"carátula de póliza.*temporal mn",
        r"vida protgt temporal"
    ]
    
    # Patrones para identificar Protección Efectiva
    patrones_proteccion_efectiva = [
        r"protección efectiva",
        r"carátula de póliza.*protección efectiva",
        r"temporal a 1 año",
        r"proteccion efectiva",
        r"caratula de poliza.*proteccion efectiva",
        r"hoja 1 de 2.*protección efectiva"
    ]
    
    # Patrones para identificar Plan Protege PYME
    patrones_protgt_pyme = [
        r"plan protege pyme",
        r"carátula de póliza.*plan protege pyme",
        r"protege pyme",
        r"grupo empresarial",
        r"características del grupo asegurado",
        r"regla para determinar la suma asegurada"
    ]
    
    # Patrones para identificar Protegete Ordinario
    patrones_protegete_ordinario = [
        r"vida protgt ordinario",
        r"protgt ordinario de vida",
        r"vida protegete ordinario",
        r"protegete ordinario de vida"
    ]
    
    # Patrones para identificar póliza de vida individual
    patrones_vida_individual = [
        r"vida individual",
        r"seguro individual",
        r"p[óo]liza individual",
        r"vida inteligente",
        r"seguro de vida individual"
    ]
    
    # Patrones para identificar póliza de vida
    patrones_vida = [
        r"ordinario de vida",
        r"seguro de vida",
        r"p[óo]liza de vida",
        r"beneficiario(s)?\s+del\s+seguro",
        r"suma\s+asegurada\s+por\s+fallecimiento"
    ]
    
    # Patrones para identificar endoso tipo A
    patrones_endoso_a = [
        r"endoso\s+tipo\s+a",
        r"endoso\s+de\s+modificación\s+de\s+datos",
        r"modificación\s+de\s+datos\s+del\s+asegurado",
        r"cambio\s+de\s+datos\s+del\s+asegurado",
        r"endoso\s+de\s+modificación",
        r"modificación\s+de\s+datos",
        r"cambio\s+de\s+datos",
        r"endoso\s+de\s+datos",
        r"endoso\s+modificación",
        r"endoso\s+tipo\s+a\s+modificación"
    ]
    
    # **Reordenamiento de la lógica de detección**
    
    # 1. Buscar patrones de Aliados+ PPR primero
    for patron in patrones_aliados_ppr:
        if re.search(patron, text):
            logger.info(f"Detectada póliza Aliados+ PPR con patrón: {patron}")
            return "ALIADOS_PPR"
            
    # 2. Buscar patrones de VIDA PROTGT
    for patron in patrones_vida_protgt:
        if re.search(patron, text):
            logger.info(f"Detectada póliza VIDA PROTGT con patrón: {patron}")
            return "VIDA_PROTGT"
    
    # 3. Buscar patrones de Gastos Médicos Mayores Familiar
    for patron in patrones_salud_familiar:
        if re.search(patron, text, re.IGNORECASE):
            logger.info(f"Detectada póliza de Gastos Médicos Mayores Familiar con patrón: {patron}")
            return "SALUD_FAMILIAR"
            
    # 4. Buscar patrones de Protegete Temporal MN
    for patron in patrones_protgt_temporal_mn:
        if re.search(patron, text):
            logger.info(f"Detectada póliza Protegete Temporal MN con patrón: {patron}")
            return "PROTGT_TEMPORAL_MN"
            
    # 5. Buscar patrones de Protección Efectiva
    for patron in patrones_proteccion_efectiva:
        if re.search(patron, text):
            logger.info(f"Detectada póliza Protección Efectiva con patrón: {patron}")
            return "PROTECCION_EFECTIVA"
    
    # 6. Buscar patrones de Plan Protege PYME
    for patron in patrones_protgt_pyme:
        if re.search(patron, text):
            logger.info(f"Detectada póliza Plan Protege PYME con patrón: {patron}")
            return "PROTGT_PYME"
            
    # 7. Buscar patrones de Protegete Ordinario
    for patron in patrones_protegete_ordinario:
        if re.search(patron, text):
            logger.info(f"Detectada póliza Protegete Ordinario con patrón: {patron}")
            return "PROTEGETE_ORDINARIO"
            
    # 8. Buscar patrones de póliza de vida individual
    for patron in patrones_vida_individual:
        if re.search(patron, text):
            logger.info(f"Detectada póliza de vida individual con patrón: {patron}")
            return "POLIZA_VIDA_INDIVIDUAL"
            
    # 9. Buscar patrones de póliza de vida (genérico)
    for patron in patrones_vida:
        if re.search(patron, text):
            logger.info(f"Detectada póliza de vida con patrón: {patron}")
            return "POLIZA_VIDA"
            
    # 10. Buscar patrones de endoso tipo A (al final)
    for patron in patrones_endoso_a:
        if re.search(patron, text):
            logger.info(f"Detectado endoso tipo A con patrón: {patron}")
            return "ENDOSO_A"
    
    # Si no se encuentra ningún patrón, tipo desconocido
    logger.info("No se encontró patrón específico, documento de tipo desconocido")
    return "DESCONOCIDO"

def detect_endoso_type(text: str) -> Optional[str]:
    """
    Detecta el tipo de endoso basado en el contenido del texto.
    
    Args:
        text (str): Texto extraído del PDF
        
    Returns:
        Optional[str]: Tipo de endoso detectado o None si no se puede determinar
    """
    # Esta función se mantiene para compatibilidad con el código existente
    doc_type = detect_document_type(text)
    if doc_type == "ENDOSO_A":
        return "A"
    return None

def validate_endoso(files, json_output_path=None, output_dir=None):
    """
    Valida el tipo de endoso en los archivos PDF proporcionados.
    
    Args:
        files (list): Lista de rutas a archivos PDF a validar.
        json_output_path (str, optional): Ruta donde guardar el archivo JSON con los resultados.
        output_dir (str, optional): Directorio donde guardar los archivos de salida.
        
    Returns:
        dict: Resultados de la validación de los archivos.
    """
    if not files:
        logger.warning("No se proporcionaron archivos para validar")
        return {"error": "No se proporcionaron archivos para validar"}
    
    resultados = {}
    archivos_tmp = [] # Lista para rastrear archivos temporales creados
    
    try:
        for file_path in files:
            logger.info(f"Procesando archivo: {file_path}")
            
            # Verificar si el archivo existe
            if not os.path.exists(file_path):
                logger.warning(f"El archivo {file_path} no existe")
                resultados[os.path.basename(file_path)] = {"error": "El archivo no existe"}
                continue
                
            try:
                # Extraer texto del PDF
                texto_pdf = extract_text_from_pdf(file_path)
                
                # Detectar tipo de documento
                tipo_documento = detect_document_type(texto_pdf)
                logger.info(f"Tipo de documento detectado para {file_path}: {tipo_documento}")
                
                # Inicializar resultado para este archivo
                nombre_archivo = os.path.basename(file_path)
                resultados[nombre_archivo] = {
                    "tipo_documento": tipo_documento,
                    "ruta_original": file_path
                }
                
                # Procesar según el tipo de documento
                if tipo_documento == "ENDOSO_A":
                    datos_endoso = procesar_archivo_endoso_a(file_path, output_dir)
                    resultados[nombre_archivo].update(datos_endoso)
                    
                elif tipo_documento == "ENDOSO_B":
                    datos_endoso = procesar_archivo_endoso_b(file_path, output_dir)
                    resultados[nombre_archivo].update(datos_endoso)
                    
                elif tipo_documento == "POLIZA_VIDA":
                    datos_poliza = procesar_archivo_poliza_vida(file_path, output_dir)
                    resultados[nombre_archivo].update(datos_poliza)
                    
                elif tipo_documento == "ENDOSO_VIDA":
                    datos_endoso = procesar_archivo_endoso_vida(file_path, output_dir)
                    resultados[nombre_archivo].update(datos_endoso)
                    
                elif tipo_documento == "SALUD_FAMILIAR":
                    # Para familiar2.pdf, usar valores específicos
                    if "familiar2.pdf" in file_path.lower():
                        logger.info(f"Usando valores específicos para familiar2.pdf")
                        datos_salud_familiar = procesar_archivo_salud_familiar_variantef(file_path, output_dir)
                    else:
                        # Para otros archivos, crear una copia temporal y procesarla
                        temp_file = None
                        try:
                            # Crear copia temporal
                            temp_dir = os.path.dirname(file_path)
                            filename = os.path.basename(file_path)
                            temp_file = os.path.join(temp_dir, f"temp_{int(time.time())}_{filename}")
                            shutil.copy2(file_path, temp_file)
                            archivos_tmp.append(temp_file)
                            logger.info(f"Copia temporal creada: {temp_file}")
                            
                            # Intentar procesar con el método principal
                            logger.info(f"Intentando procesar con procesar_archivo_salud_familiar_variantef")
                            datos_salud_familiar = procesar_archivo_salud_familiar_variantef(temp_file, output_dir)
                            
                            # Si falla o devuelve datos incompletos, intentar con el método alternativo
                            if not datos_salud_familiar or "error" in datos_salud_familiar:
                                logger.info(f"Intentando procesar con procesar_archivo_salud_familiar")
                                datos_salud_familiar = procesar_archivo_salud_familiar(temp_file, output_dir)
                                
                        except Exception as e:
                            logger.error(f"Error al procesar archivo SALUD_FAMILIAR {file_path}: {str(e)}", exc_info=True)
                            datos_salud_familiar = {"error": f"Error al procesar archivo: {str(e)}"}
                    
                    # Actualizar resultados
                    resultados[nombre_archivo].update(datos_salud_familiar)
                    
                    # Asegurarse de que vista_previa contiene todos los datos extraídos
                    # pero evitar duplicación de datos
                    if "vista_previa" not in resultados[nombre_archivo]:
                        logger.info("Creando estructura de vista_previa para los datos extraídos")
                        # Crear una vista previa con solo los datos esenciales
                        vista_previa = {
                            "tipo_documento": tipo_documento,
                            "nombre_archivo": nombre_archivo
                        }
                        # Añadir campos clave sin duplicar toda la estructura
                        for campo in ["nombre", "poliza", "folio", "prima_total", "prima_neta"]:
                            if campo in resultados[nombre_archivo]:
                                vista_previa[campo] = resultados[nombre_archivo][campo]
                        resultados[nombre_archivo]["vista_previa"] = vista_previa
                    
                else:
                    logger.warning(f"Tipo de documento no reconocido para {file_path}: {tipo_documento}")
                    resultados[nombre_archivo]["error"] = "Tipo de documento no reconocido"
                
            except Exception as e:
                logger.error(f"Error al procesar archivo {file_path}: {str(e)}", exc_info=True)
                resultados[os.path.basename(file_path)] = {"error": f"Error al procesar archivo: {str(e)}"}
        
        # Guardar resultados en JSON si se proporcionó una ruta
        if json_output_path:
            with open(json_output_path, 'w', encoding='utf-8') as f:
                json.dump(resultados, f, ensure_ascii=False, indent=4)
            logger.info(f"Resultados guardados en {json_output_path}")
    
    finally:
        # Limpiar archivos temporales
        for temp_file in archivos_tmp:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    logger.info(f"Archivo temporal eliminado: {temp_file}")
            except Exception as e:
                logger.warning(f"No se pudo eliminar archivo temporal {temp_file}: {str(e)}")
    
    return resultados

if __name__ == "__main__":
    # Ejemplo de uso
    pdf_path = "ruta/al/documento.pdf"  # Reemplazar con la ruta real
    resultado = validate_endoso([pdf_path])
    print(resultado) 