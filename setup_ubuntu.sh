#!/bin/bash

# Script para configurar entorno de desarrollo en Ubuntu para PRISMA

# Colores para mensajes
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Configurando entorno para PRISMA en Ubuntu...${NC}"

# Instalar dependencias del sistema necesarias para PyMuPDF
echo -e "${BLUE}Instalando dependencias del sistema...${NC}"
sudo apt-get update
sudo apt-get install -y build-essential python3-dev python3-pip python3-venv swig
sudo apt-get install -y libfreetype6-dev libharfbuzz-dev libfribidi-dev
sudo apt-get install -y mupdf mupdf-tools libmupdf-dev
echo -e "${GREEN}Dependencias del sistema instaladas correctamente.${NC}"

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

# Instalar requerimientos uno por uno, empezando por PyMuPDF
echo -e "${BLUE}Instalando PyMuPDF...${NC}"
pip install PyMuPDF==1.19.6 --no-build-isolation

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