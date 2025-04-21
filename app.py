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
import time

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
    # Agregar timestamp para evitar duplicaciones
    timestamp = str(int(time.time()))
    logger.info(f"Iniciando procesamiento de archivo con timestamp: {timestamp}")
    
    try:
        # Verificar si es un archivo o una URL
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            logger.info(f"Archivo subido: {file.filename}")
            
            # Guardar archivo con timestamp para evitar duplicación
            temp_filename = f"temp_{timestamp}_{secure_filename(file.filename)}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
            file.save(filepath)
            
        elif 'url' in request.form and request.form['url']:
            url = request.form['url']
            logger.info(f"URL proporcionada: {url}")
            
            # Descargar archivo
            response = requests.get(url)
            if response.status_code != 200:
                return jsonify({"error": "No se pudo descargar el archivo de la URL"}), 400
                
            # Guardar archivo con timestamp para evitar duplicación
            temp_filename = f"temp_{timestamp}_url_file.pdf"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
            with open(filepath, 'wb') as f:
                f.write(response.content)
                
        else:
            return jsonify({"error": "No se proporcionó archivo o URL"}), 400
            
        # Estructura base para la respuesta
        response_data = {
            "tipo_documento": "DESCONOCIDO",
            "descripcion": "Documento no reconocido",
            "datos_financieros": {
                "prima_neta": "0",
                "gastos_expedicion": "0",
                "iva": "0",
                "precio_total": "0",
                "tasa_financiamiento": "0",
                "prima_mensual": "0"
            },
            "datos_completos": {},
            "vista_previa": {}
        }
            
        # Intentar procesar el archivo
        try:
            logger.info(f"Procesando archivo: {filepath}")
            result = validate_endoso(filepath)
            
            if result:
                logger.info(f"Archivo procesado correctamente como: {result.get('tipo_documento', 'DESCONOCIDO')}")
                # Actualizar respuesta con los resultados
                response_data["tipo_documento"] = result.get("tipo_documento", "DESCONOCIDO")
                response_data["descripcion"] = result.get("descripcion", "Documento no reconocido")
                
                # Actualizar datos financieros si existen
                if "datos_financieros" in result and result["datos_financieros"]:
                    response_data["datos_financieros"] = result["datos_financieros"]
                
                # Actualizar datos completos si existen
                if "datos_completos" in result and result["datos_completos"]:
                    response_data["datos_completos"] = result["datos_completos"]
                
                # Manejar vista_previa para evitar duplicación
                if "vista_previa" in result and result["vista_previa"] is not None:
                    response_data["vista_previa"] = result["vista_previa"]
                elif "datos_completos" in result and result["datos_completos"]:
                    # Crear una vista previa básica si no existe
                    datos = result["datos_completos"]
                    response_data["vista_previa"] = {
                        "Número de póliza": datos.get("Número de póliza", "0"),
                        "Nombre del contratante": datos.get("Nombre del contratante", "0"),
                        "Prima Neta": datos.get("Prima Neta", "0"),
                        "I.V.A.": datos.get("I.V.A.", "0"),
                        "Prima anual total": datos.get("Prima anual total", "0")
                    }
            else:
                logger.warning(f"No se pudieron extraer datos del archivo: {filepath}")
                
        except Exception as e:
            logger.error(f"Error al procesar el archivo: {str(e)}")
            return jsonify({"error": f"Error al procesar el archivo: {str(e)}"}), 500
            
        # Eliminar archivo temporal
        try:
            os.remove(filepath)
            logger.info(f"Archivo temporal eliminado: {filepath}")
        except Exception as e:
            logger.warning(f"No se pudo eliminar el archivo temporal: {str(e)}")
            
        return jsonify(response_data)
            
    except Exception as e:
        logger.error(f"Error general en upload_file: {str(e)}")
        return jsonify({"error": f"Error en el servidor: {str(e)}"}), 500

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

@app.route('/process_pdf', methods=['POST'])
def process_pdf():
    try:
        # Verificar si se enviaron archivos
        if 'file' not in request.files:
            return jsonify({"error": "No se han enviado archivos"}), 400
            
        files = request.files.getlist('file')
        
        if not files or len(files) == 0 or files[0].filename == '':
            return jsonify({"error": "No se han seleccionado archivos"}), 400
            
        # Crear directorio temporal único para los archivos subidos
        timestamp = int(time.time())
        temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{timestamp}")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Crear directorio de salida
        output_dir = os.path.join(temp_dir, "output")
        os.makedirs(output_dir, exist_ok=True)
        
        # Guardar archivos
        saved_files = []
        for file in files:
            if file and file.filename:
                # Verificar si es un PDF
                if not file.filename.lower().endswith('.pdf'):
                    continue
                    
                # Guardar con un nombre seguro y único
                filename = f"{timestamp}_{secure_filename(file.filename)}"
                filepath = os.path.join(temp_dir, filename)
                file.save(filepath)
                saved_files.append(filepath)
                logger.info(f"Archivo guardado: {filepath}")
                
        if not saved_files:
            return jsonify({"error": "No se han guardado archivos válidos"}), 400
            
        # Definir la ruta de salida del JSON
        output_json = os.path.join(output_dir, f"resultados_{timestamp}.json")
        
        # Procesar archivos con el validador de endosos
        resultado = validate_endoso(saved_files, json_output_path=output_json, output_dir=output_dir)
        
        # Limpieza: eliminar los archivos temporales
        for filepath in saved_files:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    logger.info(f"Archivo temporal eliminado: {filepath}")
            except Exception as e:
                logger.warning(f"No se pudo eliminar archivo temporal {filepath}: {str(e)}")
        
        # Respuesta
        return jsonify({
            "message": "Archivos procesados correctamente",
            "resultado": resultado,
            "timestamp": timestamp
        })
    except Exception as e:
        logger.error(f"Error al procesar archivos: {str(e)}", exc_info=True)
        return jsonify({"error": f"Error al procesar los archivos: {str(e)}"}), 500

# Agregar función para verificar si un archivo es válido
def allowed_file(filename):
    """Verifica si el archivo tiene una extensión permitida"""
    return '.' in filename and filename.lower().endswith('.pdf')

if __name__ == '__main__':
    app.run(debug=True) 