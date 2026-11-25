# Memorias Vivas · backend

API del archivo digital y muro comunitario del pueblo Arhuaco (Iku).
Proyecto ALUNA IA — Universidad del Magdalena.

Front asociado: [`front_memorias_vivas`](https://github.com/AlexEspinosa98/front_memorias_vivas).

## La regla que ordena todo el diseño

El documento base del archivo dice que solo se incorpora lo que la comunidad
autorice compartir, y que algunos saberes son colectivos, restringidos o
reservados. Eso no quedó como una recomendación en la documentación: está en el
modelo de datos.

1. **Nada se publica sin autorización.** Una historia solo pasa a `publicado` si
   tiene al menos un registro de `Consent` (quién autoriza, en qué calidad, con
   qué alcance y bajo qué condiciones). `Story.publish()` falla si no lo hay, y
   el serializador no deja poner `status: publicado` por la vía directa.
2. **El acceso lo decide quien publica.** Cuatro niveles de visibilidad:
   `publico` (sin iniciar sesión), `registrado`, `comunidad` (solo miembros
   activos) y `restringido` (permiso nominal, uno por uno).
3. **Los saberes reservados no se mapean.** Una historia marcada como
   `is_sensitive` no puede ser de uso abierto, no expone coordenadas y queda
   fuera del endpoint del mapa.

## Puesta en marcha

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_archivo     # las 13 secciones del archivo y sus fuentes
python manage.py seed_muro        # comunidades, personas e historias de ejemplo
python manage.py runserver
```

- API: `http://127.0.0.1:8000/api/`
- Documentación OpenAPI: `http://127.0.0.1:8000/api/docs/`
- Admin: `http://127.0.0.1:8000/admin/`

Sin `DATABASE_URL` se usa SQLite. Con ella (Neon, Vercel Postgres) se usa
Postgres con SSL.

### Cuentas de demostración

`seed_muro` crea estas cuentas, todas con la clave `memorias2026`:

| Correo | Rol | Comunidad |
| --- | --- | --- |
| `admin@memoriasvivas.co` | administración | — |
| `mamo.zalabata@memoriasvivas.co` | autoridad | Nabusímake |
| `ana.izquierdo@memoriasvivas.co` | miembro | Nabusímake |
| `juan.villafane@memoriasvivas.co` | moderación | Séynimin |
| `tejedoras@memoriasvivas.co` | miembro | Ikarwa |
| `visitante@memoriasvivas.co` | visitante | — |

Son datos de prueba: ninguno es material cultural real.

## Pruebas

```bash
python manage.py test
```

27 pruebas, centradas en quién ve qué y en que nada se publique sin
autorización (`stories/tests.py`).

## Estructura

| App | Qué contiene |
| --- | --- |
| `accounts` | Usuario con correo como identificador, rol de plataforma, aceptación de los criterios de cuidado cultural. |
| `communities` | Comunidades, vínculos (`Membership`) con rol y estado, solicitudes de ingreso y su decisión. |
| `stories` | El muro: historias, materiales, autorizaciones, permisos nominales, reacciones, comentarios, visitas, promociones y reportes. |
| `catalog` | Las 13 secciones del archivo, sus figuras y las fuentes del documento base. |

## Endpoints principales

| Método y ruta | Para qué |
| --- | --- |
| `POST /api/auth/registro/` | Crear cuenta (exige aceptar los criterios de cuidado cultural). |
| `POST /api/auth/login/` | Token JWT + datos del usuario. |
| `GET /api/historias/` | El muro, ya filtrado por lo que puede ver quien consulta. |
| `POST /api/historias/` | Crear (queda en `borrador`). |
| `POST /api/historias/{id}/autorizaciones/` | Registrar la autorización de la comunidad. |
| `POST /api/historias/{id}/enviar_a_revision/` | La autoría la manda a revisión. |
| `POST /api/historias/{id}/publicar/` | Autoridad o moderación publica; falla sin autorización. |
| `POST /api/historias/{id}/accesos/` | Conceder acceso nominal a una historia restringida. |
| `POST /api/historias/{id}/aprecio/` | Reaccionar (`DELETE` para quitar). |
| `GET /api/historias/mapa/` | Puntos que pueden mostrarse (excluye lo sensible). |
| `GET /api/comunidades/` | Comunidades y el vínculo de quien consulta. |
| `POST /api/comunidades/{slug}/solicitar/` | Pedir ingreso. |
| `GET /api/archivo/` | Las secciones del archivo (consulta abierta). |

## Despliegue en Vercel

`vercel.json` y `build_files.sh` ya están listos. En el proyecto de Vercel hay
que definir:

```
DJANGO_SECRET_KEY   (una clave larga y nueva)
DJANGO_DEBUG        False
DJANGO_ALLOWED_HOSTS  .vercel.app,<su-dominio>
DATABASE_URL        la cadena de Postgres (Neon o Vercel Postgres)
CORS_ALLOWED_ORIGINS  https://<el-front>.vercel.app
```

Las migraciones se corren una vez contra esa base:

```bash
DATABASE_URL="postgres://…" python manage.py migrate
DATABASE_URL="postgres://…" python manage.py seed_archivo
```

**Pendiente antes de producción:** los archivos subidos (`MEDIA_ROOT`) se
guardan en disco, y en Vercel el sistema de archivos es efímero. Hay que
conectar un almacenamiento externo (Vercel Blob, S3 o Cloudinary) antes de que
la comunidad suba audios y fotografías.

## Nota metodológica

Este software no sustituye la consulta directa con el pueblo Arhuaco ni la
revisión de sus autoridades. Antes de registrar, transcribir, clasificar o
publicar memorias, relatos, fotografías, grabaciones o conocimientos, el equipo
debe explicar el propósito del archivo, solicitar autorización y respetar las
condiciones de acceso que defina la comunidad.
