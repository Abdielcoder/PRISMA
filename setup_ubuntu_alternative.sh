#!/bin/bash

# Script alternativo para configurar entorno de desarrollo en Ubuntu para PRISMA
# Este script intenta evitar la compilación descargando un wheel precompilado

# Colores para mensajes
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Configurando entorno para PRISMA en Ubuntu (método alternativo)...${NC}"

# Crear entorno virtual si no existe
if [ ! -d "venv" ]; then
    echo -e "${BLUE}Creando entorno virtual...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}Entorno virtual creado correctamente.${NC}"
else
    echo -e "${BLUE}El entorno virtual ya existe.${NC}"
fi

# Activar entorno virtual
echo -e "${BLUE}Activando entorno virtual...${NC}"
source venv/bin/activate

# Actualizar pip e instalar setuptools y wheel primero
echo -e "${BLUE}Actualizando pip e instalando dependencias básicas...${NC}"
pip install --upgrade pip setuptools wheel

# Determinar la arquitectura y versión de Python
ARCH=$(uname -m)
PY_VERSION=$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "${BLUE}Arquitectura detectada: ${ARCH}, Python ${PY_VERSION}${NC}"

# Instalar PyMuPDF usando la opción --only-binary para evitar compilación
echo -e "${BLUE}Instalando PyMuPDF sin compilación...${NC}"
pip install PyMuPDF==1.19.6 --only-binary=PyMuPDF

# Si falla, intentar con otra versión que tenga wheels para Python 3.12
if [ $? -ne 0 ]; then
    echo -e "${RED}No se pudo instalar PyMuPDF 1.19.6. Intentando con versión 1.21.1...${NC}"
    pip install PyMuPDF==1.21.1 --only-binary=PyMuPDF
fi

# Si sigue fallando, intentar con una versión más reciente
if [ $? -ne 0 ]; then
    echo -e "${RED}No se pudo instalar PyMuPDF 1.21.1. Intentando con versión 1.22.5...${NC}"
    pip install PyMuPDF==1.22.5 --only-binary=PyMuPDF
fi

# Si aún falla, instalar las dependencias de sistema y probar una última vez
if [ $? -ne 0 ]; then
    echo -e "${RED}Instalando dependencias del sistema para compilación...${NC}"
    sudo apt-get update
    sudo apt-get install -y build-essential python3-dev swig
    sudo apt-get install -y libfreetype6-dev libharfbuzz-dev libfribidi-dev
    sudo apt-get install -y mupdf mupdf-tools libmupdf-dev
    echo -e "${BLUE}Intentando instalar PyMuPDF con compilación...${NC}"
    pip install PyMuPDF==1.19.6
fi

# Instalar el resto de las dependencias
echo -e "${BLUE}Instalando el resto de dependencias...${NC}"
pip install PyPDF2==3.0.1
pip install Flask==2.3.3 Werkzeug==2.3.7
pip install python-dotenv==1.0.0
pip install Pillow==10.0.1
pip install numpy==1.24.3
pip install regex==2023.5.5

# Configurar variable de entorno para modo debug
echo -e "${BLUE}Configurando modo debug...${NC}"
export DEBUG=1

# Mostrar instrucciones para ejecutar
echo -e "${GREEN}Entorno configurado correctamente.${NC}"
echo -e "${BLUE}Para ejecutar el servicio:${NC}"
echo -e "  python ia_general_ws.py"
echo -e ""
echo -e "${BLUE}El servicio se iniciará con DEBUG=1 habilitado.${NC}"
echo -e "${BLUE}Para salir del entorno virtual: deactivate${NC}" 