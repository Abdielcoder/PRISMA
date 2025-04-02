from flask import Flask, render_template, request, jsonify, send_file
import os
from werkzeug.utils import secure_filename
import PyPDF2
import requests
from io import BytesIO
import json
from extract_financial import extract_financial_data, normalizar_numero
import fitz  # PyMuPDF
import base64
from urllib.parse import urlparse
import mimetypes

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit

# Asegurarse de que existe el directorio de uploads
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def is_valid_pdf_url(url):
    """Verifica si la URL apunta a un PDF válido"""
    try:
        response = requests.head(url, allow_redirects=True)
        content_type = response.headers.get('content-type', '').lower()
        return 'pdf' in content_type or url.lower().endswith('.pdf')
    except:
        return False

def get_pdf_data(file_path):
    """Lee el archivo PDF y devuelve sus datos en base64"""
    with open(file_path, 'rb') as file:
        pdf_data = file.read()
        return base64.b64encode(pdf_data).decode('utf-8')

def get_pdf_preview(file_path):
    """Genera una vista previa del PDF en base64"""
    doc = fitz.open(file_path)
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # Aumentar la calidad de la imagen
    img_data = pix.tobytes("png")
    doc.close()
    return base64.b64encode(img_data).decode('utf-8')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files and 'url' not in request.form:
        return jsonify({'error': 'No se proporcionó ningún archivo o URL'}), 400
    
    try:
        if 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No se seleccionó ningún archivo'}), 400
            
            if file and file.filename.endswith('.pdf'):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                # Extraer datos financieros
                financial_data = extract_financial_data(filepath)
                
                # Obtener vista previa y datos del PDF
                preview = get_pdf_preview(filepath)
                pdf_data = get_pdf_data(filepath)
                
                os.remove(filepath)  # Limpiar el archivo después de procesarlo
                
                return jsonify({
                    'preview': preview,
                    'pdf_data': pdf_data,
                    'financial_data': financial_data
                })
            
        elif 'url' in request.form:
            url = request.form['url']
            if not url:
                return jsonify({'error': 'URL no proporcionada'}), 400
                
            if not is_valid_pdf_url(url):
                return jsonify({'error': 'La URL no apunta a un PDF válido'}), 400
                
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                
                # Guardar temporalmente el PDF de la URL
                temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'temp.pdf')
                with open(temp_filepath, 'wb') as f:
                    f.write(response.content)
                
                # Extraer datos financieros
                financial_data = extract_financial_data(temp_filepath)
                
                # Obtener vista previa y datos del PDF
                preview = get_pdf_preview(temp_filepath)
                pdf_data = get_pdf_data(temp_filepath)
                
                os.remove(temp_filepath)  # Limpiar el archivo temporal
                
                return jsonify({
                    'preview': preview,
                    'pdf_data': pdf_data,
                    'financial_data': financial_data
                })
            except requests.exceptions.RequestException as e:
                return jsonify({'error': f'Error al descargar el PDF: {str(e)}'}), 400
            
        return jsonify({'error': 'Formato de archivo no válido'}), 400
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 