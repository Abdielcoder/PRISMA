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
        
        # Validar y procesar el endoso
        resultado = validate_endoso(file_path)
        
        if "error" in resultado:
            return jsonify(resultado), 400
        
        # Generar vista previa y datos del PDF
        preview = get_pdf_preview(file_path)
        pdf_data = get_pdf_data(file_path)
        
        # Limpiar archivo temporal
        if file_path and file_path.startswith(tempfile.gettempdir()):
            os.unlink(file_path)
        
        # Convertir los nombres de las claves al formato esperado por el frontend
        datos_financieros = resultado.get("datos_financieros", {})
        datos_formateados = {
            "Prima neta": datos_financieros.get("prima_neta", 0.0),
            "Gastos por expedición": datos_financieros.get("gastos_expedicion", 0.0),
            "I.V.A.": datos_financieros.get("iva", 0.0),
            "Precio total": datos_financieros.get("precio_total", 0.0),
            "Tasa de financiamiento": datos_financieros.get("tasa_financiamiento", 0.0)
        }
        
        return jsonify({
            "message": "Archivo procesado correctamente",
            "file_name": file_name,
            "preview": preview,
            "pdf_data": pdf_data,
            "financial_data": datos_formateados
        })
        
    except Exception as e:
        logger.error(f"Error en upload_file: {str(e)}")
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

if __name__ == '__main__':
    app.run(debug=True) 