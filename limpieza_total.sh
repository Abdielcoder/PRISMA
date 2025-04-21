#!/bin/bash

# Script para desinstalar completamente todas las librerías y reinstalar versiones específicas
# ADVERTENCIA: Este script eliminará todas las versiones de las librerías indicadas

echo "=== LIMPIEZA TOTAL DEL ENTORNO Y REINSTALACIÓN DE VERSIONES ESPECÍFICAS ==="

# 1. DESINSTALAR LIBRERÍAS PYTHON
echo "Desinstalando todas las librerías Python relacionadas..."
pip uninstall -y PyMuPDF fitz
pip uninstall -y Flask flask-cors
pip uninstall -y PyPDF2
pip uninstall -y Werkzeug
pip uninstall -y requests
pip uninstall -y python-dotenv
pip uninstall -y Pillow
pip uninstall -y numpy
pip uninstall -y regex

# 2. DESINSTALAR LIBRERÍAS HOMEBREW
echo "Desinstalando librerías Homebrew relacionadas..."
# Preguntamos antes de hacer esto ya que podría afectar otros programas
read -p "¿Desinstalar librerías de Homebrew? Esto podría afectar otros programas. (s/n): " confirmar
if [[ $confirmar == "s" || $confirmar == "S" ]]; then
    brew uninstall --ignore-dependencies mupdf swig freetype harfbuzz fribidi || true
    echo "Librerías Homebrew desinstaladas."
else
    echo "Omitiendo desinstalación de librerías Homebrew."
fi

# 3. LIMPIAR CACHÉ DE PIP
echo "Limpiando caché de pip..."
pip cache purge

# 4. INSTALAR VERSIONES ESPECÍFICAS
echo "Instalando versiones específicas de las librerías..."

# Primero instalar setuptools y wheel
pip install setuptools==68.0.0 wheel==0.41.2

# Instalar PyMuPDF de forma específica (versión 1.23.8)
echo "Instalando PyMuPDF 1.23.8..."
pip install PyMuPDF==1.23.8

# Verificar la instalación de PyMuPDF
if python -c "import fitz; print(f'PyMuPDF {fitz.version} instalado correctamente')" 2>/dev/null; then
    echo "PyMuPDF instalado correctamente."
else
    echo "ERROR: No se pudo instalar PyMuPDF correctamente."
    echo "Intentando instalar después de instalar las dependencias..."
    
    # Instalar dependencias con homebrew
    brew install mupdf swig freetype harfbuzz fribidi
    
    # Intentar de nuevo con PyMuPDF
    pip install PyMuPDF==1.23.8
fi

# Instalar el resto de las librerías
echo "Instalando otras librerías con versiones específicas..."
pip install Flask==3.0.2
pip install Werkzeug==2.3.7
pip install PyPDF2==3.0.1
pip install requests==2.31.0
pip install python-dotenv==1.0.1
pip install Flask-Cors
pip install numpy==1.24.3
pip install regex==2023.5.5

# 5. VERIFICAR INSTALACIONES
echo "Verificando instalaciones..."
python -c "import fitz; print(f'PyMuPDF: {fitz.version}')" 2>/dev/null || echo "Error: PyMuPDF no está instalado"
python -c "import flask; print(f'Flask: {flask.__version__}')" 2>/dev/null || echo "Error: Flask no está instalado"
python -c "import PyPDF2; print(f'PyPDF2: {PyPDF2.__version__}')" 2>/dev/null || echo "Error: PyPDF2 no está instalado"
python -c "import requests; print(f'Requests: {requests.__version__}')" 2>/dev/null || echo "Error: Requests no está instalado"
python -c "import dotenv; print(f'Python-dotenv: {dotenv.__version__}')" 2>/dev/null || echo "Error: Python-dotenv no está instalado"

echo "=== PROCESO COMPLETADO ==="
echo "Para probar la aplicación, ejecuta: python ia_general_ws.py" 