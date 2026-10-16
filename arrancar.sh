#!/usr/bin/env bash
# Sistema de Carnets: activa el entorno virtual y levanta el servidor.
# Uso:  bash arrancar.sh   (o doble clic si tu gestor de archivos lo permite)
set -e
cd "$(dirname "$0")"

if [ ! -f venv/bin/activate ]; then
    echo "ERROR: no existe el entorno virtual 'venv/' en esta carpeta." >&2
    exit 1
fi
source venv/bin/activate
echo "Servidor de carnets: http://localhost:8000  (Ctrl+C para detener)"
exec python manage.py runserver
