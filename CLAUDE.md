# CLAUDE.md

Guía para Claude Code al trabajar en este repositorio.

## Qué es

API de Memorias Vivas: archivo digital y muro comunitario del pueblo Arhuaco
(Iku), del proyecto ALUNA IA. Django 5.2 + DRF + Postgres (SQLite en local).
El front vive en `front_memorias_vivas` (Next.js 16).

Lea `README.md` para el arranque y `docs/PROPUESTA_IA.md` para el plan de IA.

## La regla que no se negocia

Este archivo existe bajo una condición cultural: solo se publica lo que la
comunidad autoriza. Está codificada en tres lugares y **no debe debilitarse**
sin discutirlo primero:

1. `Story.publish()` y `Story.clean()` — una historia no pasa a `publicado`
   sin al menos un `Consent`.
2. `StoryQuerySet.visible_for(user)` y `Story.can_be_seen_by(user)` — el
   filtro de visibilidad. Toda vista nueva que devuelva historias debe partir
   de uno de los dos; nunca de `Story.objects.all()`.
3. `Story.public_location` y la acción `mapa` — el contenido con
   `is_sensitive=True` no expone coordenadas ni aparece en el mapa.

Cualquier cambio en estos tres puntos debe venir con pruebas en
`stories/tests.py`, que es donde están cubiertos.

## Comandos

```bash
source .venv/bin/activate

python manage.py migrate
python manage.py seed_archivo        # 13 secciones del archivo + fuentes
python manage.py seed_muro           # datos de demostración del muro
python manage.py seed_muro --reset   # los vuelve a crear desde cero
python manage.py runserver

python manage.py test                # suite completa (27 pruebas)
python manage.py test stories.tests.VisibilityQuerySetTests
```

Sin `DATABASE_URL` en `.env` se usa SQLite. Con ella, Postgres con SSL.

## Apps

- `accounts` — usuario por correo, rol de plataforma, aceptación de criterios
  de cuidado cultural. Los helpers `community_ids()` y
  `authority_community_ids()` son la base de casi todos los permisos.
- `communities` — comunidades y `Membership` (rol + estado). El rol dentro de
  una comunidad vive aquí, no en `User`.
- `stories` — el muro. El archivo grande del proyecto es `stories/models.py`;
  su docstring explica las tres reglas.
- `catalog` — las 13 secciones editoriales y las fuentes. Consulta abierta.

## Convenciones

- Rutas de la API y campos de cara al usuario en español
  (`/api/historias/`, `/api/comunidades/{slug}/solicitar/`); nombres de código
  en inglés.
- Los textos de `verbose_name`, `help_text` y errores van en español: los lee
  la comunidad en el admin.
- Los contadores de `Story` (`like_count`, `comment_count`) son
  desnormalizados. Recalcúlelos con `story.recount()`, que consulta por
  `story_id` para no leer una caché de `prefetch_related`.
- La publicación no se hace con `PATCH status`: el serializador lo rechaza a
  propósito. Se usa la acción `publicar/`.
