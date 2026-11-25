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
2. **Framework preset: Django.** Vercel lo detecta solo por el `manage.py`,
   lee `WSGI_APPLICATION` de `settings.py` y carga `application` desde
   `memorias_vivas/wsgi.py`. Instala `requirements.txt` y corre
   `collectstatic` por su cuenta.

   Este repositorio **no tiene `vercel.json` ni carpeta `api/`**, y así debe
   quedarse: la detección nativa se encarga de todo. Solo haría falta un
   `vercel.json` para ajustar la función (por ejemplo `maxDuration`), con la
   clave `memorias_vivas/wsgi.py`.

   > **Si el proyecto ya existía en Vercel con la configuración vieja**, hay
   > que limpiarlo: en *Settings → General*, dejar el Framework Preset en
   > `Django` y quitar cualquier Build Command, Output Directory o Install
   > Command sobreescrito. Después, *Deployments → Redeploy* **sin** caché.
   >
   > Dos errores conocidos de configuraciones viejas:
   > - `externally-managed-environment` en el build: venía de un script
   >   `build_files.sh` con `pip install`. El Python de la imagen de build lo
   >   gestiona `uv` y rechaza instalar encima.
   > - **404 de Vercel en todas las rutas** (página «Not Found» sencilla, sin
   >   traza de Django): venía de un `vercel.json` con `rewrites` hacia
   >   `/api/index`. Si ve ese 404, revise que no queden ni `vercel.json` ni
   >   `api/` en el repositorio.
3. En **Environment Variables**, antes del primer despliegue:

| Variable | Valor |
| --- | --- |
| `DATABASE_URL` | la cadena con `-pooler` de Neon |
| `DJANGO_SECRET_KEY` | una clave nueva y larga (ver abajo) |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_ALLOWED_HOSTS` | `.vercel.app` |
| `CSRF_TRUSTED_ORIGINS` | `https://*.vercel.app` |

> **CORS no se configura aquí.** Está abierto desde `settings.py`
> (`CORS_ALLOW_ALL_ORIGINS = True`), sin depender de ninguna variable, para
> que el front funcione desde producción, desde cualquier vista previa de
> Vercel y desde localhost sin mantener listas.
>
> Es seguro porque la autenticación va por token Bearer, no por cookie:
> `CORS_ALLOW_CREDENTIALS = False` impide que el navegador mande cookies de
> sesión desde otro dominio. Y CORS no decide qué datos salen — eso lo sigue
> resolviendo `StoryQuerySet.visible_for()` en cada petición.
>
> Si alguna vez hay que cerrarlo, el bloque comentado al final de la sección
> CORS de `settings.py` tiene la lista lista para descomentar.

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

## Encender las funciones de IA (opcional)

El revisor de cuidado cultural **funciona sin nada de esto**, con la lista de
términos que mantiene la comunidad. Lo que sigue solo hace falta para el
asistente de consulta y para la segunda mirada del revisor.

### 1. Sacar la clave

1. Entrar a <https://aistudio.google.com/apikey> con una cuenta de Google.
2. *Create API key*, y elegir un proyecto (o dejar que cree uno).
3. Copiar la clave. Se ve una sola vez; si se pierde, se crea otra.

La clave es un secreto: no va al repositorio ni a un chat. Va en `.env`
(ignorado por git) y en las variables de entorno de Vercel.

### 2. Averiguar el nombre del modelo

No lo adivine ni lo copie de un blog: los nombres cambian y uno equivocado
falla. Pregúnteselo a su propia clave:

```bash
GEMINI_API_KEY="su-clave" python manage.py ia_estado --modelos
```

Lista los modelos que esa clave acepta y termina sugiriendo cuál usar:

```
  Para este proyecto sirve:  GEMINI_MODEL=<el que salga>
```

Un modelo «flash» alcanza de sobra y es el más barato.

### 3. Probarlo en local antes de desplegar

Con las dos variables en `.env`:

```bash
python manage.py ia_estado
```

```bash
python manage.py ia_estado --probar "¿cómo se aprende a tejer una mochila?"
```

La primera muestra qué está configurado y qué activó cada comunidad; la
segunda hace una consulta real y muestra la respuesta con sus fuentes.

Pruebe también un tema vedado — `--probar "cómo se hace un pagamento"` — y
verifique que responde `estado: vedada` sin llamar al modelo.

### 4. Ponerlas en Vercel

En el proyecto del **backend**, *Settings → Environment Variables*:

| Variable | Valor |
| --- | --- |
| `GEMINI_API_KEY` | la clave de AI Studio |
| `GEMINI_MODEL` | el id que sugirió `--modelos` |

Redesplegar para que las tome.

### 5. Activar la función en cada comunidad

Nada corre hasta que la comunidad lo autorice. En el admin, *Comunidades* →
la comunidad → campo **funciones de IA activadas**:

```json
{"revisor_cuidado": true}
```

Para que además el texto pueda salir hacia Gemini, hay que agregar el
sufijo `_externo`, que es una decisión aparte:

```json
{"revisor_cuidado": true, "revisor_cuidado_externo": true}
```

Aun así, el contenido sensible y el de acceso restringido nunca salen del
servidor: eso está en el código, no en la configuración.

### Sobre el costo

El plan gratuito de Google AI Studio alcanza para un prototipo, pero las
cuotas cambian y conviene revisarlas en su propia consola antes de una
demostración. Si la cuota se agota, el asistente responde que no está
disponible y el revisor sigue funcionando con reglas: nada se rompe.

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
