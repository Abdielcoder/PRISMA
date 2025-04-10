from flask import Flask, request, jsonify
import requests
import re
import logging
import tempfile
import shutil
import os
import sys
import json
from pathlib import Path
import importlib.util
import io

# --- IMPORTACIÓN DE MÓDULOS DE EXTRACTORES ---
# Función para importar módulos dinámicamente
def importar_modulo(nombre_archivo):
    try:
        spec = importlib.util.spec_from_file_location(nombre_archivo, nombre_archivo)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return modulo
    except Exception as e:
        logging.error(f"Error al importar módulo {nombre_archivo}: {str(e)}")
        return None

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Importar extractores
try:
    validador_tipo_endoso = importar_modulo("validar_tipo_endoso.py")
    endosos_autos = importar_modulo("endosos_autos_a.py")
    data_ia_general_vida = importar_modulo("data_ia_general_vida.py")
    data_ia_general_salud_familiar = importar_modulo("data_ia_general_salud_familiar.py")
    data_ia_general_salud_familiar_variantef = importar_modulo("data_ia_general_salud_familiar_variantef.py")
    data_ia_general_salud_colectivo = importar_modulo("data_ia_general_salud_colectivo.py")
    data_ia_general_vida_individual = importar_modulo("data_ia_general_vida_individual.py")
    data_ia_general_protgt_ppr = importar_modulo("data_ia_general_protgt_ppr.py")
    data_ia_general_vida_protgt = importar_modulo("data_ia_general_vida_protgt.py")
    data_ia_general_protgt_mn = importar_modulo("data_ia_general_protgt_mn.py")
    data_ia_general_proteccion_efectiva = importar_modulo("data_ia_general_proteccion_efectiva.py")
    data_ia_general_protgt_pyme = importar_modulo("data_ia_general_protgt_pyme.py")
    
    if validador_tipo_endoso:
        logging.info("Módulo validar_tipo_endoso.py cargado correctamente")
    else:
        logging.error("No se pudo cargar validar_tipo_endoso.py. La detección de documentos podría ser imprecisa.")
except Exception as e:
    logging.error(f"Error al cargar los módulos: {str(e)}")

app = Flask(__name__)

class PolizaProcessor:
    def __init__(self):
        self.extractores = {}
        self.cargar_extractores()
    
    def cargar_extractores(self):
        """Carga los extractores disponibles"""
        # Extractor de endosos de autos
        if 'endosos_autos' in globals():
            self.extractores["ENDOSO_A"] = endosos_autos.extraer_datos_endoso_a
        
        # Extractores de pólizas de vida y salud
        if 'data_ia_general_vida' in globals():
            self.extractores["POLIZA_VIDA"] = data_ia_general_vida.extraer_datos_poliza_vida
        
        if 'data_ia_general_salud_familiar' in globals():
            self.extractores["SALUD_FAMILIAR"] = data_ia_general_salud_familiar.extraer_datos_poliza_salud_familiar
        
        if 'data_ia_general_salud_familiar_variantef' in globals():
            self.extractores["SALUD_FAMILIAR_VARIANTEF"] = data_ia_general_salud_familiar_variantef.extraer_datos_poliza_salud_familiar_variantef
        
        if 'data_ia_general_salud_colectivo' in globals():
            self.extractores["SALUD_COLECTIVO"] = data_ia_general_salud_colectivo.extraer_datos_poliza_salud_colectivo
        
        if 'data_ia_general_vida_individual' in globals():
            self.extractores["POLIZA_VIDA_INDIVIDUAL"] = data_ia_general_vida_individual.extraer_datos_poliza_vida_individual
        
        if 'data_ia_general_protgt_ppr' in globals():
            self.extractores["POLIZA_ALIADOS_PPR"] = data_ia_general_protgt_ppr.extraer_datos_poliza_aliados_ppr
        
        if 'data_ia_general_vida_protgt' in globals():
            self.extractores["POLIZA_VIDA_PROTGT"] = data_ia_general_vida_protgt.extraer_datos_poliza_vida_protgt
        
        if 'data_ia_general_protgt_mn' in globals():
            self.extractores["POLIZA_PROTGT_TEMPORAL_MN"] = data_ia_general_protgt_mn.extraer_datos_poliza_protgt_temporal_mn
        
        if 'data_ia_general_proteccion_efectiva' in globals():
            self.extractores["PROTECCION_EFECTIVA"] = data_ia_general_proteccion_efectiva.extraer_datos_poliza_proteccion_efectiva
        
        if 'data_ia_general_protgt_pyme' in globals():
            self.extractores["PROTGT_PYME"] = data_ia_general_protgt_pyme.extraer_datos_poliza_protgt_pyme
        
        logging.info(f"Extractores cargados: {list(self.extractores.keys())}")

    def detectar_tipo_documento(self, pdf_path):
        """Detecta el tipo de documento para seleccionar el extractor apropiado"""
        try:
            # Usar el validador importado globalmente
            if 'validador_tipo_endoso' in globals() and validador_tipo_endoso:
                try:
                    resultado = validador_tipo_endoso.validate_endoso(pdf_path)
                    if resultado and "tipo_documento" in resultado:
                        tipo = resultado["tipo_documento"]
                        descripcion = resultado.get("descripcion", "")
                        logging.info(f"Validador detectó: {tipo} - {descripcion}")
                        return tipo, resultado
                    else:
                        logging.warning("El validador no pudo determinar el tipo de documento o devolvió un formato no esperado")
                except Exception as e:
                    logging.error(f"Error al usar validador_tipo_endoso: {str(e)}")
            else:
                logging.warning("validador_tipo_endoso no está disponible")
            
            # Detección alternativa si validador falló
            # Detectar ENDOSO_A
            if 'endosos_autos' in globals() and hasattr(endosos_autos, 'detectar_formato'):
                try:
                    texto = endosos_autos.extraer_texto_pdf(pdf_path)
                    formato = endosos_autos.detectar_formato(texto)
                    if formato != "FORMATO_DESCONOCIDO":
                        return "ENDOSO_A", None
                except Exception as e:
                    logging.warning(f"Error al detectar formato endosos_autos: {str(e)}")
            
            # Intentar con data_ia_general_salud_colectivo (prioridad alta por ser nuevo)
            if 'data_ia_general_salud_colectivo' in globals():
                try:
                    # Extraer texto para la detección
                    import fitz
                    doc = fitz.open(pdf_path)
                    texto = ""
                    for page in doc:
                        texto += page.get_text("text") + "\n"
                    doc.close()
                    
                    # Intentar detectar con la función específica
                    if hasattr(data_ia_general_salud_colectivo, 'detectar_tipo_documento'):
                        tipo_detectado = data_ia_general_salud_colectivo.detectar_tipo_documento(texto)
                        logging.info(f"Detector salud_colectivo devolvió: {tipo_detectado}")
                        if tipo_detectado == "SALUD_COLECTIVO":
                            logging.info("Tipo de documento identificado como Salud Colectivo")
                            return "SALUD_COLECTIVO", None
                    else:
                        logging.warning("El módulo data_ia_general_salud_colectivo no tiene función detectar_tipo_documento")
                except Exception as e:
                    logging.warning(f"Error al intentar detección con data_ia_general_salud_colectivo: {str(e)}")
            
            # Intentar con cada detector específico
            for tipo, extractor in self.extractores.items():
                if tipo != "ENDOSO_A" and tipo != "SALUD_COLECTIVO":  # Ya intentamos estos
                    try:
                        # Intentar usar función de detección específica si existe
                        modulo_nombre = f"data_ia_general_{tipo.lower()}"
                        if modulo_nombre in globals():
                            modulo = globals()[modulo_nombre]
                            if hasattr(modulo, 'detectar_tipo_documento'):
                                texto = ""
                                # Extraer texto para la detección
                                import fitz
                                doc = fitz.open(pdf_path)
                                for page in doc:
                                    texto += page.get_text("text") + "\n"
                                doc.close()
                                
                                detectado = modulo.detectar_tipo_documento(texto)
                                if detectado != "DESCONOCIDO":
                                    logging.info(f"Tipo de documento identificado como {tipo}")
                                    return tipo, None
                                else:
                                    logging.warning(f"Tipo de documento no identificado como {tipo}")
                    except Exception as ex:
                        logging.warning(f"Error al intentar detección con {tipo}: {str(ex)}")
            
            logging.error("No se pudo determinar el tipo de documento")
            return "DESCONOCIDO", None
            
        except Exception as e:
            logging.error(f"Error en detección de tipo de documento: {str(e)}")
            return "DESCONOCIDO", None

    def formatear_datos_financieros(self, datos, tipo_documento):
        """Formatea los datos financieros para el API"""
        datos_financieros = {}
        
        if tipo_documento == "ENDOSO_A":
            # Mapeo para ENDOSO_A
            datos_financieros = {
                "prima_neta": datos.get("prima_neta", "0"),
                "gastos_expedicion": datos.get("gastos_expedicion", "0"),
                "iva": datos.get("iva", "0"),
                "precio_total": datos.get("precio_total", "0"),
                "tasa_financiamiento": datos.get("tasa_financiamiento", "0"),
                "prima_mensual": datos.get("prima_mensual", "0"),
                "ramo": datos.get("ramo", "AUTOS"),
                "tipo_endoso": datos.get("tipo_endoso", "A - MODIFICACIÓN DE DATOS")
            }
        else:
            # Mapeo general para pólizas
            # Asegurarse de que manejamos correctamente diferentes formatos de nombres de campos
            campos_mapeados = {
                "Prima Neta": "prima_neta",
                "Prima anual total": "precio_total",
                "Gastos de Expedición": "gastos_expedicion",
                "I.V.A.": "iva",
                "Prima base I.V.A.": "prima_base_iva",
                "Descuento familiar": "descuento_familiar",
                "Cesión de Comisión": "cesion_comision",
                "Recargo por pago fraccionado": "recargo_pago_fraccionado"
            }
            
            for campo_origen, campo_destino in campos_mapeados.items():
                if campo_origen in datos:
                    datos_financieros[campo_destino] = datos[campo_origen]
                elif campo_destino not in datos_financieros:
                    datos_financieros[campo_destino] = "0"
        
        return datos_financieros

    def _procesar_tipo_pago(self, datos):
        """
        Procesa el tipo de pago, extrayéndolo del campo nombre si existe
        y asegurando que solo haya un tipo de pago en los datos
        """
        # Limpiar campos con saltos de línea y contenido adicional
        for campo, valor in list(datos.items()):
            if isinstance(valor, str):
                # Detectar si hay información adicional después de un salto de línea
                if '\n' in valor:
                    # Tomar solo la primera línea
                    datos[campo] = valor.split('\n')[0].strip()
        
        # Primero limpiar nombres que contienen "Tipo de pago"
        campos_a_limpiar = ["Nombre del contratante", "Nombre del asegurado titular", "Nombre del plan"]
        tipo_pago_encontrado = None
        
        for campo in campos_a_limpiar:
            if campo in datos and isinstance(datos[campo], str):
                # Buscar "Tipo de pago" en el campo
                tipo_pago_pattern = r'(.+?)\s+Tipo\s+de\s+pago\s+(.+)'
                match = re.search(tipo_pago_pattern, datos[campo], re.IGNORECASE)
                if match:
                    # Limpiar el nombre
                    datos[campo] = match.group(1).strip()
                    # Guardar el tipo de pago si es la primera ocurrencia
                    if not tipo_pago_encontrado:
                        tipo_pago_encontrado = match.group(2).strip()
        
        # Si ya encontramos un tipo de pago en los nombres, usarlo
        if tipo_pago_encontrado:
            datos["Tipo de pago"] = tipo_pago_encontrado
            return
            
        # Verificar si ya existe un campo específico para tipo de pago
        if "Tipo de pago" in datos:
            # Si tiene salto de línea, tomar solo el primer valor
            if isinstance(datos["Tipo de pago"], str) and '\n' in datos["Tipo de pago"]:
                datos["Tipo de pago"] = datos["Tipo de pago"].split('\n')[0].strip()
            return
        
        # Buscar en campos como Nombre del plan o Nombre del contratante
        campos_posibles = ["Nombre del plan", "Nombre del contratante", "Nombre del asegurado titular"]
        
        # Patrones para detectar tipo de pago
        patrones_tipo_pago = [
            r'ANUAL',
            r'MENSUAL',
            r'SEMESTRAL',
            r'TRIMESTRAL',
            r'BIMESTRAL',
            r'QUINCENAL',
            r'TARJETA\s+DE\s+CR[EÉ]DITO'
        ]
        
        for campo in campos_posibles:
            if campo in datos and datos[campo] != "0":
                for patron in patrones_tipo_pago:
                    if re.search(patron, datos[campo], re.IGNORECASE):
                        tipo_pago_encontrado = re.search(patron, datos[campo], re.IGNORECASE).group(0).title()
                        # Limpiar el nombre extrayendo el tipo de pago
                        datos[campo] = re.sub(r'\s*' + patron + r'\s*', ' ', datos[campo], flags=re.IGNORECASE).strip()
                        break
                if tipo_pago_encontrado:
                    break
        
        # Si encontramos un tipo de pago, agregarlo como campo separado
        if tipo_pago_encontrado:
            datos["Tipo de pago"] = tipo_pago_encontrado
        # Si existe frecuencia de pago, usarla como tipo de pago
        elif "Frecuencia de pago" in datos and datos["Frecuencia de pago"] != "0":
            datos["Tipo de pago"] = datos["Frecuencia de pago"]
            
    def _normalizar_fechas(self, datos):
        """
        Normaliza fechas en diferentes formatos a un formato estándar.
        Procesa fechas con formatos:
        - DD/MM/YYYY
        - DD/MMM/YYYY (donde MMM es el mes en texto como ENE, FEB, MAR, etc.)
        """
        if not datos:
            return
            
        # Mapeo de meses en español a su número
        meses = {
            "ENE": "01", "FEB": "02", "MAR": "03", "ABR": "04", "MAY": "05", "JUN": "06",
            "JUL": "07", "AGO": "08", "SEP": "09", "OCT": "10", "NOV": "11", "DIC": "12",
            # Variaciones o abreviaturas alternativas
            "ENERO": "01", "FEBRERO": "02", "MARZO": "03", "ABRIL": "04", "MAYO": "05", "JUNIO": "06",
            "JULIO": "07", "AGOSTO": "08", "SEPTIEMBRE": "09", "OCTUBRE": "10", "NOVIEMBRE": "11", "DICIEMBRE": "12"
        }
        
        # Campos de fecha a normalizar
        campos_fecha = ["Fecha de emisión", "Fecha de inicio de vigencia", "Fecha de fin de vigencia"]
        
        for campo in campos_fecha:
            if campo in datos and datos[campo] not in ["0", "No disponible"]:
                fecha = datos[campo]
                # Detectar si es formato DD/MMM/YYYY
                match = re.search(r'(\d{2})/([A-Za-z]{3,})/(\d{4})', fecha, re.IGNORECASE)
                if match:
                    dia = match.group(1)
                    mes_texto = match.group(2).upper()
                    año = match.group(3)
                    
                    # Convertir el mes de texto a número
                    if mes_texto in meses:
                        mes_num = meses[mes_texto]
                        # Formatear a DD/MM/YYYY
                        fecha_normalizada = f"{dia}/{mes_num}/{año}"
                        datos[campo] = fecha_normalizada
                        logging.info(f"Fecha normalizada: {campo} = {fecha} -> {fecha_normalizada}")
                    else:
                        logging.warning(f"No se pudo normalizar la fecha {campo}: {fecha} - Mes no reconocido: {mes_texto}")
        
        return datos
            
    def process_pdf(self, pdf_url: str) -> dict:
        """Procesa un PDF desde una URL y extrae su información"""
        temp_dir = tempfile.mkdtemp()
        pdf_path = Path(temp_dir) / "documento.pdf"

        try:
            # Descargar PDF
            response = requests.get(
                pdf_url,
                headers={'Accept': 'application/pdf'},
                timeout=30
            )
            response.raise_for_status()

            if 'application/pdf' not in response.headers.get('Content-Type', ''):
                raise ValueError("El archivo no es un PDF válido")
            
            # Guardar PDF temporalmente
            pdf_path.write_bytes(response.content)
            
            # **1. Definir la estructura base completa con valores por defecto**
            # Incluir TODOS los campos posibles de todos los extractores
            respuesta_poliza_base = {
                # Campos generales
                "Clave Agente": "No disponible", 
                "Coaseguro": "No disponible", 
                "Cobertura Básica": "No disponible",
                "Cobertura Nacional": "No disponible", 
                "Código Postal": "No disponible", 
                "Deducible": "No disponible", 
                "Deducible Cero por Accidente": "No disponible",
                "Domicilio del asegurado": "No disponible", 
                "Domicilio del contratante": "No disponible",
                "Fecha de emisión": "No disponible", 
                "Fecha de fin de vigencia": "No disponible",
                "Fecha de inicio de vigencia": "No disponible", 
                "Frecuencia de pago": "No disponible",
                "Gama Hospitalaria": "No disponible", 
                "I.V.A.": "0.00", 
                "Nombre del agente": "No disponible",
                "Nombre del asegurado titular": "No disponible", 
                "Nombre del contratante": "No disponible",
                "Nombre del plan": "No disponible", 
                "Número de póliza": "No disponible",
                "Periodo de pago de siniestro": "No disponible", 
                "Plazo de pago": "No disponible",
                "Prima Neta": "0.00", 
                "Prima anual total": "0.00", 
                "Prima mensual": "0.00", 
                "Derecho de póliza": "0.00",
                "R.F.C.": "No disponible", 
                "Teléfono": "No disponible", 
                "Url": "No disponible", 
                "Suma asegurada": "0.00", 
                "Moneda": "No disponible",
                
                # Campos específicos para pólizas de salud
                "Descuento familiar": "0.00", 
                "Cesión de Comisión": "0.00", 
                "Recargo por pago fraccionado": "0.00",
                "Zona Tarificación": "No disponible",
                "Ciudad del contratante": "No disponible",
                "Ciudad del asegurado": "No disponible",
                "Tope de Coaseguro": "No disponible",
                "Tipo de Red": "No disponible",
                "Tabulador Médico": "No disponible",
                "Emergencias en el Extranjero": "No disponible",
                "Medicamentos fuera del hospital": "No disponible",
                "Maternidad": "No disponible",
                "Protección Dental": "No disponible",
                "Tu Médico 24 Hrs": "No disponible",
                "Complicaciones de GMM no cubiertos": "No disponible",
                "Tipo de plan solicitado": "No disponible",
                
                # Campos específicos para pólizas de vida
                "Tipo de Plan": "No disponible",
                "Solicitud": "No disponible",
                "Subramo": "No disponible",
                "Tipo de pago": "No disponible",
                "Suma asegurada por fallecimiento": "0.00",
                "Fondo de reserva": "0.00",
                "Contratante": "No disponible",
                "Promotor": "No disponible",
                "Beneficiarios": [],
                
                # Campos para planes PYME
                "Características del grupo asegurado": "No disponible",
                "Regla para determinar la suma asegurada": "No disponible",
                "Nombre de la empresa": "No disponible",
                "Giro de la empresa": "No disponible",
                
                # Coberturas y adicionales para todos los tipos de pólizas
                "Coberturas Incluidas": [],
                "Coberturas Adicionales": [],
                "Servicios con Costo": []
            }

            # **2. Detectar el tipo de documento y procesar**
            tipo_documento, resultado_validacion = self.detectar_tipo_documento(pdf_path)
            
            if tipo_documento == "DESCONOCIDO":
                return {
                    "error": "No se pudo determinar el tipo de documento"
                }
            
            # **3. Procesar con el extractor adecuado**
            datos_completos_extraidos = None
            datos_financieros = None
            descripcion = ""
            
            if resultado_validacion and "datos_completos" in resultado_validacion:
                # Usar datos del validador si están disponibles
                datos_completos_extraidos = resultado_validacion.get("datos_completos", {})
                datos_financieros = resultado_validacion.get("datos_financieros", {})
                descripcion = resultado_validacion.get("descripcion", "")
                logging.info(f"Usando datos completos del validador para {tipo_documento}")
            else:
                # Usar extractor específico
                if tipo_documento in self.extractores:
                    try:
                        extractor = self.extractores[tipo_documento]
                        datos_completos_extraidos = extractor(pdf_path)
                        
                        # Formatear datos financieros
                        datos_financieros = self.formatear_datos_financieros(datos_completos_extraidos, tipo_documento)
                        
                        # Establecer descripción basada en el tipo de documento
                        descripcion_dict = {
                            "ENDOSO_A": "MODIFICACIÓN DE DATOS",
                            "POLIZA_VIDA": "PÓLIZA DE VIDA",
                            "POLIZA_VIDA_INDIVIDUAL": "PÓLIZA DE VIDA INDIVIDUAL",
                            "SALUD_FAMILIAR": "PÓLIZA DE GASTOS MÉDICOS FAMILIAR",
                            "SALUD_FAMILIAR_VARIANTEF": "PÓLIZA DE GASTOS MÉDICOS FAMILIAR (VARIANTE F)",
                            "POLIZA_ALIADOS_PPR": "PÓLIZA ALIADOS+ PPR",
                            "POLIZA_VIDA_PROTGT": "PÓLIZA VIDA PROTGT",
                            "POLIZA_PROTGT_TEMPORAL_MN": "PÓLIZA PROTGT TEMPORAL MN",
                            "PROTECCION_EFECTIVA": "PÓLIZA PROTECCIÓN EFECTIVA",
                            "PROTGT_PYME": "PLAN PROTEGE PYME",
                            "SALUD_COLECTIVO": "PÓLIZA DE GASTOS MÉDICOS COLECTIVO"
                        }
                        descripcion = descripcion_dict.get(tipo_documento, "DOCUMENTO DESCONOCIDO")
                        
                        logging.info(f"Datos extraídos mediante extractor específico para {tipo_documento}")
                    except Exception as e:
                        logging.error(f"Error al extraer datos con el extractor para {tipo_documento}: {str(e)}")
                        return {
                            "error": f"Error al procesar el documento: {str(e)}"
                        }
                else:
                    logging.error(f"No hay extractor disponible para {tipo_documento}")
                    return {
                        "error": "No se encontró un extractor adecuado para este tipo de documento"
                    }
            
            # **4. Rellenar estructura base con datos extraídos**
            if datos_completos_extraidos:
                # Eliminar campos que no deben estar en la respuesta
                campos_a_excluir = []
                
                for key, value in datos_completos_extraidos.items():
                    # Transferir todos los campos a la respuesta base
                    # Si el campo no está en la estructura base, lo añadimos
                    if key not in campos_a_excluir:
                        if key not in respuesta_poliza_base:
                            # Añadir el campo nuevo a la estructura base
                            respuesta_poliza_base[key] = value
                            logging.info(f"Campo nuevo añadido a la respuesta: {key}")
                        else:
                            # Actualizar valor si no es "0" o None
                            if value is not None and value != "0":
                                respuesta_poliza_base[key] = value
            
            # Extraer tipo de pago del campo nombre si existe
            self._procesar_tipo_pago(datos_completos_extraidos)
            
            # Normalizar fechas en diferentes formatos
            self._normalizar_fechas(datos_completos_extraidos)
            
            # Rellenar la estructura base con datos completos extraídos
            if datos_completos_extraidos:
                for key, value in datos_completos_extraidos.items():
                    # Si el valor es diferente de "0" o None, actualizar en la estructura base
                    if value is not None and value != "0" and key in respuesta_poliza_base:
                        respuesta_poliza_base[key] = value

            # **5. Preparar respuesta financiera**
            respuesta_financiera_base = {
                "prima_neta": "0.00",
                "gastos_expedicion": "0.00",
                "iva": "0.00",
                "precio_total": "0.00",
                "tasa_financiamiento": "0.00",
                "prima_mensual": "0.00",
                "descuento_familiar": "0.00",
                "cesion_comision": "0.00",
                "recargo_pago_fraccionado": "0.00",
                "ramo": "OTRO",
                "tipo_endoso": descripcion
            }
            
            # Rellenar datos financieros si existen
            if datos_financieros:
                for key, value in datos_financieros.items():
                    if key in respuesta_financiera_base:
                        respuesta_financiera_base[key] = value
            
            # Asegurarse de que los datos financieros incluyan el ramo y tipo_endoso
            if tipo_documento == "ENDOSO_A":
                ramo = "AUTOS"
                respuesta_financiera_base["ramo"] = ramo
                respuesta_financiera_base["tipo_endoso"] = descripcion or "A - MODIFICACIÓN DE DATOS"
            elif tipo_documento == "POLIZA_ALIADOS_PPR":
                ramo = "VIDA"
                respuesta_financiera_base["ramo"] = ramo 
                respuesta_financiera_base["tipo_endoso"] = descripcion or "PÓLIZA ALIADOS+ PPR"
            elif tipo_documento == "POLIZA_PROTGT_TEMPORAL_MN":
                ramo = "VIDA"
                respuesta_financiera_base["ramo"] = ramo
                respuesta_financiera_base["tipo_endoso"] = descripcion or "PÓLIZA PROTGT TEMPORAL MN"
            elif tipo_documento == "POLIZA_VIDA_PROTGT":
                ramo = "VIDA"
                respuesta_financiera_base["ramo"] = ramo
                respuesta_financiera_base["tipo_endoso"] = descripcion or "PÓLIZA VIDA PROTGT"
            elif tipo_documento == "PROTECCION_EFECTIVA":
                ramo = "VIDA"
                respuesta_financiera_base["ramo"] = ramo
                respuesta_financiera_base["tipo_endoso"] = descripcion or "PÓLIZA PROTECCIÓN EFECTIVA"
            elif tipo_documento == "POLIZA_VIDA":
                ramo = "VIDA"
                respuesta_financiera_base["ramo"] = ramo
                respuesta_financiera_base["tipo_endoso"] = descripcion or "PÓLIZA DE VIDA"
            elif tipo_documento == "PROTGT_PYME":
                ramo = "PYME"
                respuesta_financiera_base["ramo"] = ramo
                respuesta_financiera_base["tipo_endoso"] = descripcion or "PLAN PROTEGE PYME"
            elif tipo_documento in ["SALUD_FAMILIAR", "SALUD_FAMILIAR_VARIANTEF", "SALUD_COLECTIVO"]:
                ramo = "SALUD"
                respuesta_financiera_base["ramo"] = ramo
                respuesta_financiera_base["tipo_endoso"] = descripcion or "PÓLIZA DE GASTOS MÉDICOS FAMILIAR"
            else:
                # Para cualquier otro tipo de documento, usar valores genéricos
                ramo = "OTRO"
                respuesta_financiera_base["ramo"] = ramo
                respuesta_financiera_base["tipo_endoso"] = descripcion or "DOCUMENTO"
                
            # Para documentos de salud familiar, asegurar que los campos especiales estén incluidos
            if tipo_documento in ["SALUD_FAMILIAR", "SALUD_FAMILIAR_VARIANTEF", "SALUD_COLECTIVO"]:
                logging.info(f"Preparando datos para documento de salud {tipo_documento}")
                logging.info(f"Descuento familiar: {respuesta_poliza_base['Descuento familiar']}")
                logging.info(f"Cesión de Comisión: {respuesta_poliza_base['Cesión de Comisión']}")
                logging.info(f"Recargo por pago fraccionado: {respuesta_poliza_base['Recargo por pago fraccionado']}")
                
                # Obtener el valor de Prima anual total desde los datos financieros si no está en los datos de la póliza
                if respuesta_poliza_base.get("Prima anual total") == "0.00" and respuesta_financiera_base.get("Precio total") != "0.00":
                    respuesta_poliza_base["Prima anual total"] = respuesta_financiera_base.get("Precio total")
                    
                # Obtener valor de I.V.A. desde los datos financieros si no está en los datos de la póliza
                if respuesta_poliza_base.get("I.V.A.") == "0.00" and respuesta_financiera_base.get("I.V.A.") != "0.00":
                    respuesta_poliza_base["I.V.A."] = respuesta_financiera_base.get("I.V.A.")
                    
                # Asegurar que estos valores también estén en la respuesta financiera
                respuesta_financiera_base["Descuento familiar"] = respuesta_poliza_base.get("Descuento familiar", "0.00")
                respuesta_financiera_base["Cesión de Comisión"] = respuesta_poliza_base.get("Cesión de Comisión", "0.00")
                respuesta_financiera_base["Recargo por pago fraccionado"] = respuesta_poliza_base.get("Recargo por pago fraccionado", "0.00")
                
                # Asignar URL para condiciones generales según tipo
                if respuesta_poliza_base.get("Url") == "No disponible":
                    if tipo_documento == "SALUD_FAMILIAR_VARIANTEF":
                        respuesta_poliza_base["Url"] = "https://rinoapps.com/condiciones/salud_familiar_variantef.pdf"
                    elif tipo_documento == "SALUD_COLECTIVO":
                        respuesta_poliza_base["Url"] = "https://rinoapps.com/condiciones/salud_colectivo.pdf"
                    else:
                        respuesta_poliza_base["Url"] = "https://rinoapps.com/condiciones/salud_familiar.pdf"
            
            # Respuesta final
            respuesta = {
                "tipo_documento": tipo_documento,
                "descripcion": descripcion,
                "datos_financieros": respuesta_financiera_base,
                "datos_completos": respuesta_poliza_base
            }
            
            return respuesta
        
        except Exception as e:
            logging.error(f"Error al procesar PDF: {str(e)}")
            return {"error": str(e)}
            
        finally:
            # Limpiar archivos temporales
            if pdf_path.exists():
                pdf_path.unlink()
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logging.warning(f"Error al eliminar directorio temporal {temp_dir}: {str(e)}")

processor = PolizaProcessor()

@app.route('/polizas', methods=['POST'])
def process_policy():
    try:
        pdf_url = request.json.get('pdf_url')
        if not pdf_url:
            return jsonify({'error': 'URL requerida'}), 400

        # Procesar el PDF
        result = processor.process_pdf(pdf_url)
        
        # Crear estructura de respuesta plana
        respuesta = {}
        
        # Agregar datos financieros y de póliza directamente al objeto raíz
        for key, value in result.items():
            if key not in ["tipo_documento", "descripcion", "ramo"]:
                respuesta[key] = value
        
        # Agregar información adicional que pueda ser útil
        respuesta["document_type"] = result.get("tipo_documento", "DESCONOCIDO")
        respuesta["description"] = result.get("descripcion", "")
        respuesta["ramo"] = result.get("ramo", "DESCONOCIDO")
        
        return jsonify({'data': respuesta})

    except Exception as e:
        logger.error(f"Error procesando póliza: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/batch', methods=['POST'])
def process_batch():
    try:
        pdf_urls = request.json.get('pdf_urls', [])
        if not pdf_urls:
            return jsonify({'error': 'Se requiere una lista de URLs en pdf_urls'}), 400
        
        results = []
        for url in pdf_urls:
            try:
                # Procesar el PDF
                result = processor.process_pdf(url)
                
                # Crear estructura de respuesta plana
                respuesta = {}
                
                # Agregar datos financieros y de póliza directamente al objeto raíz
                for key, value in result.items():
                    if key not in ["tipo_documento", "descripcion", "ramo"]:
                        respuesta[key] = value
                
                # Agregar información adicional que pueda ser útil
                respuesta["document_type"] = result.get("tipo_documento", "DESCONOCIDO")
                respuesta["description"] = result.get("descripcion", "")
                respuesta["ramo"] = result.get("ramo", "DESCONOCIDO")
                
                results.append({
                    'url': url,
                    'status': 'success',
                    'data': respuesta
                })
            except Exception as e:
                results.append({
                    'url': url,
                    'status': 'error',
                    'error': str(e)
                })
        
        return jsonify({'results': results})
        
    except Exception as e:
        logger.error(f"Error procesando batch de pólizas: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    # Verificar que los extractores estén cargados
    extractores_cargados = list(processor.extractores.keys())
    
    # Verificar si el validador está disponible
    validador_activo = 'validador_tipo_endoso' in globals() and validador_tipo_endoso is not None
    
    return jsonify({
        'status': 'ok', 
        'service': 'ia_general_ws',
        'extractores_disponibles': extractores_cargados,
        'validador_activo': validador_activo
    })

@app.route('/validador/estado', methods=['GET'])
def validador_estado():
    """Endpoint para verificar el estado del validador"""
    if 'validador_tipo_endoso' in globals() and validador_tipo_endoso is not None:
        return jsonify({
            'status': 'ok',
            'message': 'El validador de tipo de endoso está activo y funcionando',
            'disponible': True
        })
    else:
        return jsonify({
            'status': 'warning',
            'message': 'El validador de tipo de endoso no está disponible',
            'disponible': False
        }), 200

if __name__ == '__main__':
    # Verificar si el validador está disponible al inicio
    if 'validador_tipo_endoso' in globals() and validador_tipo_endoso is not None:
        logging.info("Iniciando servidor con validador_tipo_endoso activo")
    else:
        logging.warning("Iniciando servidor SIN validador_tipo_endoso. La detección de documentos puede ser imprecisa")
    
    app.run(host='0.0.0.0', port=5009) 