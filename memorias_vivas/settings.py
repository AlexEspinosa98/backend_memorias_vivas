"""
Configuración de Django para Memorias Vivas.

Archivo digital comunitario del pueblo Arhuaco (Iku).
El acceso a los contenidos lo decide la comunidad: ver `stories.models.Visibility`.
"""
from datetime import timedelta
from pathlib import Path

import os
import sys

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "dev-insecure-memorias-vivas-cambiar-en-produccion-0123456789",
)
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,.vercel.app")

CSRF_TRUSTED_ORIGINS = [
    origin
    for origin in env_list("CSRF_TRUSTED_ORIGINS", "https://*.vercel.app")
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # terceros
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    # propias
    "accounts",
    "communities",
    "stories",
    "catalog",
    "ai",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "memorias_vivas.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "memorias_vivas.wsgi.application"

# --- Base de datos -------------------------------------------------------
# Sin DATABASE_URL se usa SQLite (desarrollo local).
# En Vercel se define DATABASE_URL apuntando a Neon (Postgres serverless).
#
# En serverless cada petición puede caer en un contenedor nuevo, así que no
# tiene sentido mantener conexiones abiertas: se usa la cadena *con pooler*
# de Neon (el host lleva `-pooler`) y `conn_max_age=0`, que deja el manejo de
# conexiones al pooler. Fuera de serverless conviene reutilizarlas.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
SERVERLESS = env_bool("VERCEL", False) or bool(os.getenv("VERCEL_ENV"))

# Las pruebas nunca tocan la base real: con DATABASE_URL apuntando a Neon,
# `manage.py test` crearía y borraría una base en el servidor de producción.
RUNNING_TESTS = "test" in sys.argv
if RUNNING_TESTS:
    DATABASE_URL = ""

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=0 if SERVERLESS else 600,
            ssl_require=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Sin manifiesto a propósito: si `collectstatic` no llegara a correr, el
    # almacenamiento con manifiesto tumba el admin entero con un 500. Con
    # WHITENOISE_USE_FINDERS los estáticos se encuentran igual.
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
# Vercel corre `collectstatic` solo y sirve los estáticos desde su CDN; con
# esta opción los recoge directamente de las apps y STATIC_ROOT no es crítico.
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = DEBUG

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- DRF ----------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 12,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", 60))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", 7))),
    "ROTATE_REFRESH_TOKENS": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Memorias Vivas API",
    "DESCRIPTION": (
        "Archivo digital y muro comunitario del pueblo Arhuaco (Iku). "
        "Los contenidos solo se publican con autorización de la comunidad."
    ),
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# --- CORS ----------------------------------------------------------------
# Abierto desde el backend: el front funciona desde cualquier dominio
# (producción, vistas previas de Vercel, localhost) sin mantener listas ni
# variables de entorno.
#
# Esto es seguro aquí por una razón concreta: la autenticación va por token
# Bearer en la cabecera, no por cookie. `CORS_ALLOW_CREDENTIALS = False` hace
# que el navegador nunca mande cookies de sesión en una petición de otro
# dominio. Abrir CORS *y* permitir credenciales sí sería peligroso: dejaría
# que cualquier página hiciera peticiones con la sesión del admin.
#
# Lo que esto NO cambia: quién puede ver qué. Eso lo sigue decidiendo
# `StoryQuerySet.visible_for()` en cada petición. CORS solo gobierna desde qué
# página del navegador se puede llamar a la API, no qué devuelve.
#
# Es incondicional a propósito: no depende de ninguna variable de entorno, así
# que una variable vieja o mal escrita en Vercel no puede volver a dejar el
# front sin poder hablar con la API.
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = False

# Para cerrarlo el día que haga falta, cambie lo de arriba por una lista:
#   CORS_ALLOW_ALL_ORIGINS = False
#   CORS_ALLOWED_ORIGINS = ["https://front-memorias-vivas.vercel.app"]
#   CORS_ALLOWED_ORIGIN_REGEXES = [r"^https://front-memorias-vivas-[\w-]+\.vercel\.app$"]

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    # Un año. Vercel ya sirve todo por HTTPS; esto evita el primer salto en claro.
    SECURE_HSTS_SECONDS = 31_536_000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
