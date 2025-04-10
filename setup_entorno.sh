#!/bin/bash

# Script para configurar el entorno de desarrollo para PRISMA

# Colores para mensajes
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Configurando entorno para PRISMA...${NC}"

# Crear entorno virtual si no existe
if [ ! -d "venv" ]; then
    echo -e "${BLUE}Creando entorno virtual...${NC}"
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error al crear el entorno virtual. Asegúrate de tener python3-venv instalado.${NC}"
        exit 1
    fi
    echo -e "${GREEN}Entorno virtual creado correctamente.${NC}"
else
    echo -e "${BLUE}El entorno virtual ya existe.${NC}"
fi

# Activar entorno virtual
echo -e "${BLUE}Activando entorno virtual...${NC}"
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo -e "${RED}Error al activar el entorno virtual.${NC}"
    exit 1
fi

# Instalar requerimientos
echo -e "${BLUE}Instalando dependencias...${NC}"
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo -e "${RED}Error al instalar las dependencias.${NC}"
    exit 1
fi
echo -e "${GREEN}Dependencias instaladas correctamente.${NC}"

# Configurar variable de entorno para modo debug
echo -e "${BLUE}Configurando modo debug...${NC}"
export DEBUG=1

# Indicaciones para ejecutar el servicio
echo -e "${GREEN}Entorno configurado correctamente.${NC}"
echo -e "${BLUE}Para ejecutar el servicio:${NC}"
echo -e "  python ia_general_ws.py"
echo -e ""
echo -e "${BLUE}El servicio se iniciará con DEBUG=1 habilitado.${NC}"
echo -e "${BLUE}Para salir del entorno virtual: deactivate${NC}" 