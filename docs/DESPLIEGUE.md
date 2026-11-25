# Despliegue: Neon + Vercel

Backend en Vercel con Postgres en Neon, front en Vercel.

---

## 1. Crear la base en Neon

1. Entrar a <https://neon.com> y crear una cuenta (sirve con la de GitHub).
2. Crear un proyecto. Al crearlo pedirá:
   - **Nombre**: `memorias-vivas`
   - **Postgres version**: la que venga por defecto
   - **Región**: la más cercana a Colombia — normalmente `AWS us-east-1`
     (Virginia) o `aws-us-east-2` (Ohio). Importa para la latencia.
3. Al terminar muestra la cadena de conexión. **Copiar la que dice «Pooled
   connection»**: el host lleva `-pooler` en el nombre.

```
postgresql://usuario:clave@ep-algo-123456-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require
                                            ^^^^^^^ esta parte
```

> La cadena contiene la contraseña de la base. No se pega en el repositorio,
> ni en el README, ni en un chat. Va en `.env` (que está en `.gitignore`) y en
> las variables de entorno de Vercel.

---

## 2. Preparar la base desde su máquina

Las migraciones y las semillas se corren una sola vez, desde local, contra
Neon. Primero guarde la cadena en el `.env` del backend:

```
DATABASE_URL=postgresql://…-pooler…?sslmode=require
```

Y después:

```bash
cd backend_memorias_vivas
source .venv/bin/activate
python manage.py migrate
python manage.py seed_archivo
python manage.py createsuperuser
```

`seed_archivo` crea las 13 secciones y las fuentes. `seed_muro` es opcional:
crea comunidades e historias de demostración, útil para mostrar el prototipo,
pero no debería quedar en la base final.

Para verificar que quedó bien:

```bash
python manage.py shell -c "from catalog.models import ArchiveSection; print(ArchiveSection.objects.count())"
```

Debe imprimir `13`.

Cuando quiera volver a trabajar en local con SQLite, basta con comentar la
línea `DATABASE_URL` del `.env`.

---

## 3. Desplegar el backend en Vercel

1. En Vercel: **Add New → Project** e importar
   `AlexEspinosa98/backend_memorias_vivas`.
2. Framework preset: **Other**. No hay que tocar los comandos de build ni el
   directorio de salida: el runtime de Python de Vercel detecta `api/index.py`,
   instala `requirements.txt` por su cuenta y `vercel.json` manda todas las
   rutas a esa función.

   > Si ve el error `externally-managed-environment` en el log de build, el
   > proyecto está usando una configuración vieja con `builds` y un script
   > `build_files.sh`. Esa forma ya no funciona: el Python de la imagen de
   > build lo gestiona `uv` y rechaza `pip install`. La configuración actual
   > del repositorio no usa script de build.
3. En **Environment Variables**, antes del primer despliegue:

| Variable | Valor |
| --- | --- |
| `DATABASE_URL` | la cadena con `-pooler` de Neon |
| `DJANGO_SECRET_KEY` | una clave nueva y larga (ver abajo) |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_ALLOWED_HOSTS` | `.vercel.app` |
| `CORS_ALLOWED_ORIGINS` | la URL del front, con `https://` y sin barra final |
| `CSRF_TRUSTED_ORIGINS` | `https://*.vercel.app` |

Para generar la clave:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

4. Desplegar. Para comprobar que quedó vivo:
   - `https://<backend>.vercel.app/` → `{"status": "ok", …}`
   - `https://<backend>.vercel.app/api/archivo/` → las 13 secciones
   - `https://<backend>.vercel.app/api/docs/` → la documentación de la API

---

## 4. Desplegar el front

1. Importar `AlexEspinosa98/front_memorias_vivas`. Vercel detecta Next.js solo.
2. Una variable:

```
NEXT_PUBLIC_API_URL = https://<backend>.vercel.app/api
```

3. Desplegar, y después volver al proyecto del backend y poner la URL real del
   front en `CORS_ALLOWED_ORIGINS`. Sin eso el navegador bloquea las llamadas y
   el muro se ve vacío sin explicar por qué.

---

## 5. Cada vez que cambien los modelos

Vercel no corre migraciones: hay que hacerlo desde local, con el `.env`
apuntando a Neon, **antes** de que el despliegue nuevo entre en servicio.

```bash
python manage.py makemigrations
python manage.py migrate        # con DATABASE_URL de Neon en .env
git push                        # esto dispara el despliegue
```

---

## Lo que todavía no funciona en Vercel

**Las fotografías y los audios.** `MEDIA_ROOT` escribe en disco y en Vercel el
sistema de archivos es efímero: lo que alguien suba se pierde en el siguiente
despliegue. El muro funciona sin materiales adjuntos, así que para el prototipo
se puede dejar así, pero antes de que la comunidad suba audios de verdad hay
que conectar un almacenamiento externo (Vercel Blob o Cloudinary). Son unas
veinte líneas cambiando `STORAGES["default"]` en `settings.py`.

**La IA de `docs/PROPUESTA_IA.md`.** Las funciones serverless tienen límite de
tiempo y no tienen GPU: la transcripción y los embeddings necesitan un servidor
aparte con cola de trabajos. Eso no cambia nada de este despliegue, el muro
sigue en Vercel.

---

## Notas sobre el plan gratuito de Neon

El plan gratuito alcanza de sobra para el prototipo, pero tiene una
particularidad que conviene conocer: **la base se suspende sola tras unos
minutos sin uso**. La primera petición después de la pausa tarda uno o dos
segundos de más mientras despierta. No es un error del despliegue; si en una
demostración importa, basta con abrir la página un minuto antes.
