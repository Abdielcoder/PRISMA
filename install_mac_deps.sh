#!/bin/bash

# Script para instalar dependencias de sistema para PyMuPDF en macOS
# Requiere tener Homebrew instalado (https://brew.sh)

# Colores para mensajes
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Instalando dependencias de sistema para PyMuPDF en macOS...${NC}"

# Verificar si Homebrew está instalado
if ! command -v brew &> /dev/null; then
    echo -e "${RED}Homebrew no está instalado. Por favor instálalo primero: https://brew.sh${NC}"
    exit 1
fi

# Actualizar Homebrew
echo -e "${BLUE}Actualizando Homebrew...${NC}"
brew update

# Instalar dependencias necesarias
echo -e "${BLUE}Instalando dependencias...${NC}"
brew install swig freetype harfbuzz fribidi

echo -e "${GREEN}Dependencias instaladas correctamente.${NC}"
echo -e "${BLUE}Ahora puedes ejecutar ./setup_entorno.sh para configurar el entorno Python.${NC}" 