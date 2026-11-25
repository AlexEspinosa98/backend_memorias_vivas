"""
Punto de entrada WSGI.

Vercel detecta el proyecto por `manage.py`, lee `WSGI_APPLICATION` de
`settings.py` y carga `application` desde aquí. No hace falta `vercel.json`
ni una carpeta `api/`.
"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "memorias_vivas.settings")

application = get_wsgi_application()
