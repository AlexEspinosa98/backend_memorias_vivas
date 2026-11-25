"""
Punto de entrada de Vercel.

El runtime de Python de Vercel busca los archivos de `api/` y espera una
aplicación WSGI o ASGI exportada como `app`. Instala `requirements.txt` por
su cuenta: no hace falta un script de build.

Los estáticos del admin los sirve WhiteNoise con `WHITENOISE_USE_FINDERS`,
así que tampoco hace falta `collectstatic` (ver `memorias_vivas/settings.py`).
"""
import os
import sys
from pathlib import Path

# La raíz del repositorio, para que `import memorias_vivas` funcione desde api/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "memorias_vivas.settings")

from memorias_vivas.wsgi import application  # noqa: E402

app = application
