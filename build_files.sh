#!/usr/bin/env bash
# Build de Vercel: instala dependencias y recolecta estáticos del admin de Django.
set -euo pipefail

pip install -r requirements.txt
python manage.py collectstatic --noinput --clear
