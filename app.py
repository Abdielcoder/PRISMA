from flask import Flask, render_template, request, jsonify, send_file
import os
from werkzeug.utils import secure_filename
import PyPDF2
import requests
from io import BytesIO
import json
from endosos_autos_a import extraer_datos_endoso_a
import fitz  # PyMuPDF
import base64
from urllib.parse import urlparse
import mimetypes
import tempfile
import logging
from validar_tipo_endoso import validate_endoso
from PIL import Image
import io
import traceback

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'loads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit

# Asegurarse de que existe el directorio de uploads
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
# Asegurarse de que existe el directorio de output para datos de procesamiento
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'output'), exist_ok=True)

def download_pdf(url):
    """Descarga un PDF desde una URL y lo guarda temporalmente."""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Crear archivo temporal
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        
        # Guardar el contenido
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                temp_file.write(chunk)
        
        temp_file.close()
        return temp_file.name
    except Exception as e:
        logger.error(f"Error al descargar PDF: {str(e)}")
        return None

def get_pdf_preview(file_path):
    """Genera una vista previa del PDF en formato base64."""
    try:
        doc = fitz.open(file_path)
        page = doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # Aumentar calidad
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # Convertir a base64
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        doc.close()
        return img_str
    except Exception as e:
        logger.error(f"Error al generar vista previa: {str(e)}")
        return None

def get_pdf_data(file_path):
    """Lee el archivo PDF y lo devuelve en formato base64."""
    try:
        with open(file_path, 'rb') as file:
            pdf_data = file.read()
            return base64.b64encode(pdf_data).decode()
    except Exception as e:
        logger.error(f"Error al leer PDF: {str(e)}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files and 'url' not in request.form:
            return jsonify({"error": "No se proporcionó archivo ni URL"}), 400
        
        file_path = None
        file_name = None
        
        # Procesar archivo subido
        if 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                return jsonify({"error": "No se seleccionó ningún archivo"}), 400
            if not file.filename.lower().endswith('.pdf'):
                return jsonify({"error": "El archivo debe ser un PDF"}), 400
            
            file_name = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
            file.save(file_path)
        
        # Procesar URL
        elif 'url' in request.form:
            url = request.form['url']
            if not url.lower().endswith('.pdf'):
                return jsonify({"error": "La URL debe apuntar a un PDF"}), 400
            
            file_path = download_pdf(url)
            if not file_path:
                return jsonify({"error": "No se pudo descargar el PDF"}), 400
            file_name = os.path.basename(url)
        
        # Validar y procesar el documento
        resultado = validate_endoso(file_path)
        
        if "error" in resultado:
            return jsonify(resultado), 400
        
        # Generar vista previa y datos del PDF
        preview = get_pdf_preview(file_path)
        pdf_data = get_pdf_data(file_path)
        
        # Limpiar archivo temporal
        if file_path and file_path.startswith(tempfile.gettempdir()):
            os.unlink(file_path)
        
        # **1. Definir la estructura base completa con valores por defecto**
        respuesta_poliza_base = {
            "Clave Agente": "No disponible", "Coaseguro": "No disponible", "Cobertura Básica": "No disponible",
            "Cobertura Nacional": "No disponible", 
            "Código Postal": "No disponible", "Deducible": "No disponible", "Deducible Cero por Accidente": "No disponible",
            "Domicilio del asegurado": "No disponible", "Domicilio del contratante": "No disponible",
            "Fecha de emisión": "No disponible", "Fecha de fin de vigencia": "No disponible",
            "Fecha de inicio de vigencia": "No disponible", "Frecuencia de pago": "No disponible",
            "Gama Hospitalaria": "No disponible", "I.V.A.": "0.00", "Nombre del agente": "No disponible",
            "Nombre del asegurado titular": "No disponible", "Nombre del contratante": "No disponible",
            "Nombre del plan": "No disponible", "Número de póliza": "No disponible",
            "Periodo de pago de siniestro": "No disponible", "Plazo de pago": "No disponible",
            "Prima Neta": "0.00", "Prima anual total": "0.00", "Prima mensual": "0.00", 
            "R.F.C.": "No disponible", "Teléfono": "No disponible", "Url": "No disponible", 
            "Suma asegurada": "0.00", "Moneda": "No disponible",
            "Descuento familiar": "0.00", "Cesión de Comisión": "0.00", "Recargo por pago fraccionado": "0.00"
            # Añadir aquí cualquier otro campo que pueda existir en algún formato
        }

        respuesta_financiera_base = {
            "Prima neta": "0.00",
            "Gastos por expedición": "0.00",
            "I.V.A.": "0.00",
            "Precio total": "0.00",
            "Tasa de financiamiento": "0.00",
            "Prima mensual": "0.00",
            "Descuento familiar": "0.00",
            "Cesión de Comisión": "0.00",
            "Recargo por pago fraccionado": "0.00"
        }

        # **2. Rellenar datos desde el resultado del procesamiento**
        datos_completos_extraidos = resultado.get("datos_completos")
        datos_financieros_extraidos = resultado.get("datos_financieros")

        if datos_completos_extraidos:
            logger.info(f"Rellenando estructura base con datos_completos para {resultado.get('descripcion')}")
            # Eliminar "Coberturas adicionales con costo" de datos_completos_extraidos si existe
            if "Coberturas adicionales con costo" in datos_completos_extraidos:
                logger.info("Eliminando campo 'Coberturas adicionales con costo' de los datos")
                del datos_completos_extraidos["Coberturas adicionales con costo"]
                
            for key, default_value in respuesta_poliza_base.items():
                # Usar el valor extraído si existe y no es "0" o None (a menos que el default sea numérico)
                valor_extraido = datos_completos_extraidos.get(key)
                if valor_extraido is not None and valor_extraido != "0":
                    respuesta_poliza_base[key] = str(valor_extraido) # Convertir a string por si acaso
                # Si el valor extraído es None o "0", pero el default es numérico ("0.00"), mantener "0.00"
                elif (valor_extraido is None or valor_extraido == "0") and isinstance(default_value, str) and default_value == "0.00":
                     respuesta_poliza_base[key] = "0.00"
                # En otros casos (valor no encontrado o es "0" y default no es numérico), mantener default
                
        if datos_financieros_extraidos:
             logger.info(f"Rellenando estructura financiera base con datos_financieros para {resultado.get('descripcion')}")
             # Mapear claves de backend a frontend
             respuesta_financiera_base["Prima neta"] = datos_financieros_extraidos.get("prima_neta", "0.00")
             respuesta_financiera_base["Gastos por expedición"] = datos_financieros_extraidos.get("gastos_expedicion", "0.00")
             respuesta_financiera_base["I.V.A."] = datos_financieros_extraidos.get("iva", "0.00")
             respuesta_financiera_base["Precio total"] = datos_financieros_extraidos.get("precio_total", "0.00")
             respuesta_financiera_base["Tasa de financiamiento"] = datos_financieros_extraidos.get("tasa_financiamiento", "0.00")
             respuesta_financiera_base["Prima mensual"] = datos_financieros_extraidos.get("prima_mensual", "0.00")
             # Agregar mapeo para los nuevos campos de pólizas de salud familiar
             respuesta_financiera_base["Descuento familiar"] = datos_financieros_extraidos.get("descuento_familiar", "0.00")
             respuesta_financiera_base["Cesión de Comisión"] = datos_financieros_extraidos.get("cesion_comision", "0.00")
             respuesta_financiera_base["Recargo por pago fraccionado"] = datos_financieros_extraidos.get("recargo_pago_fraccionado", "0.00")
             
             # Registrar los datos financieros para depuración
             logger.info(f"Datos financieros mapeados: {json.dumps(respuesta_financiera_base, ensure_ascii=False, indent=2)}")

        # **3. Formatear valores numéricos en ambas estructuras**
        campos_numericos_poliza = ["Prima Neta", "Prima anual total", "Prima mensual", "Suma asegurada", "I.V.A."]
        for key in campos_numericos_poliza:
            if key in respuesta_poliza_base:
                 try:
                     valor_num = float(str(respuesta_poliza_base[key]).replace(',',''))
                     respuesta_poliza_base[key] = f"{valor_num:.2f}"
                 except (ValueError, TypeError):
                      respuesta_poliza_base[key] = "0.00" # Default si la conversión falla

        for key in respuesta_financiera_base:
            try:
                valor_num = float(str(respuesta_financiera_base[key]).replace(',',''))
                respuesta_financiera_base[key] = f"{valor_num:.2f}"
            except (ValueError, TypeError):
                 respuesta_financiera_base[key] = "0.00"

        # Asegurarse de que los datos financieros incluyan el ramo y tipo_endoso para el frontend
        if resultado.get("tipo_documento") == "ENDOSO_A":
            respuesta_financiera_base["ramo"] = "AUTOS"
            respuesta_financiera_base["tipo_endoso"] = resultado.get("descripcion") or "A - MODIFICACIÓN DE DATOS"
        elif resultado.get("tipo_documento") == "POLIZA_ALIADOS_PPR":
            respuesta_financiera_base["ramo"] = "VIDA"
            respuesta_financiera_base["tipo_endoso"] = resultado.get("descripcion") or "PÓLIZA ALIADOS+ PPR"
        elif resultado.get("tipo_documento") == "POLIZA_PROTGT_TEMPORAL_MN":
            respuesta_financiera_base["ramo"] = "VIDA"
            respuesta_financiera_base["tipo_endoso"] = resultado.get("descripcion") or "PÓLIZA PROTGT TEMPORAL MN"
        elif resultado.get("tipo_documento") == "POLIZA_VIDA_PROTGT":
            respuesta_financiera_base["ramo"] = "VIDA"
            respuesta_financiera_base["tipo_endoso"] = resultado.get("descripcion") or "PÓLIZA VIDA PROTGT"
        elif resultado.get("tipo_documento") == "PROTECCION_EFECTIVA":
            respuesta_financiera_base["ramo"] = "VIDA"
            respuesta_financiera_base["tipo_endoso"] = resultado.get("descripcion") or "PÓLIZA PROTECCIÓN EFECTIVA"
        elif resultado.get("tipo_documento") == "POLIZA_VIDA":
            respuesta_financiera_base["ramo"] = "VIDA"
            respuesta_financiera_base["tipo_endoso"] = resultado.get("descripcion") or "PÓLIZA DE VIDA"
        elif resultado.get("tipo_documento") == "PROTGT_PYME":
            respuesta_financiera_base["ramo"] = "PYME"
            respuesta_financiera_base["tipo_endoso"] = resultado.get("descripcion") or "PLAN PROTEGE PYME"
        elif resultado.get("tipo_documento") == "SALUD_FAMILIAR":
            respuesta_financiera_base["ramo"] = "SALUD"
            respuesta_financiera_base["tipo_endoso"] = resultado.get("descripcion") or "PÓLIZA DE GASTOS MÉDICOS FAMILIAR"
        else:
            # Para cualquier otro tipo de documento, usar valores genéricos
            respuesta_financiera_base["ramo"] = "OTRO"
            respuesta_financiera_base["tipo_endoso"] = resultado.get("descripcion") or "DOCUMENTO"

        # Preparar la respuesta final JSON
        respuesta = {
            "message": "Archivo procesado correctamente",
            "file_name": file_name,
            "preview": preview,
            "pdf_data": pdf_data,
            "financial_data": respuesta_financiera_base, # Estructura financiera rellenada y formateada
            "poliza_data": respuesta_poliza_base,      # Estructura completa de póliza rellenada y formateada
            "document_type": resultado.get("tipo_documento", "DESCONOCIDO"), # Mantener para info
            "description": resultado.get("descripcion", "")              # Mantener para info
        }
        
        # Para documentos de salud familiar, asegurar que los campos especiales estén incluidos en la respuesta
        if resultado.get("tipo_documento") == "SALUD_FAMILIAR":
            logger.info("Preparando respuesta para documento de salud familiar")
            logger.info(f"Descuento familiar: {respuesta_poliza_base['Descuento familiar']}")
            logger.info(f"Cesión de Comisión: {respuesta_poliza_base['Cesión de Comisión']}")
            logger.info(f"Recargo por pago fraccionado: {respuesta_poliza_base['Recargo por pago fraccionado']}")
            
            # Asegurar que estos valores también estén en la respuesta financiera
            respuesta["financial_data"]["Descuento familiar"] = respuesta_poliza_base.get("Descuento familiar", "0.00")
            respuesta["financial_data"]["Cesión de Comisión"] = respuesta_poliza_base.get("Cesión de Comisión", "0.00")
            respuesta["financial_data"]["Recargo por pago fraccionado"] = respuesta_poliza_base.get("Recargo por pago fraccionado", "0.00")
        
        logger.debug(f"Respuesta final a jsonify: {json.dumps(respuesta, ensure_ascii=False, indent=2)}")
        return jsonify(respuesta)
        
    except Exception as e:
        logger.error(f"Error en upload_file: {str(e)}")
        logger.exception("Detalle del error en upload_file:") 
        return jsonify({"error": str(e)}), 500

@app.route('/pdf_preview/<path:filename>')
def pdf_preview(filename):
    try:
        return send_file(
            os.path.join(app.config['UPLOAD_FOLDER'], filename),
            mimetype='application/pdf'
        )
    except Exception as e:
        logger.error(f"Error al servir PDF: {str(e)}")
        return jsonify({"error": str(e)}), 404

@app.route('/api/validate', methods=['POST'])
def validate_file():
    try:
        # Verificar si se envió un archivo
        if 'file' not in request.files:
            return jsonify({'error': 'No se envió ningún archivo'}), 400
        
        file = request.files['file']
        
        # Verificar si el nombre del archivo está vacío
        if file.filename == '':
            return jsonify({'error': 'Nombre de archivo vacío'}), 400
        
        # Verificar si es un archivo PDF
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'El archivo debe ser un PDF'}), 400
        
        # Crear directorio temporal si no existe
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        # Guardar el archivo temporalmente
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
        file.save(file_path)
        
        # Validar el tipo de documento
        result = validate_endoso(file_path)
        
        if 'error' in result:
            return jsonify(result), 400
        
        # Actualizar la respuesta según el tipo de documento
        response = {
            'success': True,
            'tipo_documento': result.get('tipo_documento', 'DESCONOCIDO'),
            'descripcion': result.get('descripcion', 'Documento Desconocido'),
            'datos_financieros': result.get('datos_financieros', {})
        }
        
        # Agregar datos específicos según el tipo de documento
        if result.get('tipo_documento') == 'ENDOSO_A':
            response['tipo_endoso'] = result.get('tipo_endoso', '')
        elif result.get('tipo_documento') in ['POLIZA_VIDA', 'POLIZA_ALIADOS_PPR', 'POLIZA_PROTGT_TEMPORAL_MN', 'POLIZA_VIDA_PROTGT', 'PROTECCION_EFECTIVA', 'PROTGT_PYME', 'SALUD_FAMILIAR']:
            response['datos_completos'] = result.get('datos_completos', {})
            
            # Generar URL markdown
            if 'datos_completos' in result and 'file_path' in result.get('datos_completos', {}):
                md_file = result['datos_completos'].get('file_path', '')
                if md_file and os.path.exists(md_file):
                    response['markdown_url'] = f"/markdown/{os.path.basename(md_file)}"
        
        # Eliminar el archivo temporal después de procesarlo
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Error al eliminar archivo temporal: {str(e)}")
        
        return jsonify(response), 200
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True) 