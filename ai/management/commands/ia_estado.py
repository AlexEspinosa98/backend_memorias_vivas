"""
Diagnóstico de la capa de IA.

    python manage.py ia_estado             # qué hay configurado y qué funciona
    python manage.py ia_estado --modelos   # modelos que acepta SU clave
    python manage.py ia_estado --probar "¿cómo se teje una mochila?"

Sirve, sobre todo, para resolver la pregunta de «¿qué pongo en GEMINI_MODEL?»
sin adivinar: `--modelos` pregunta por los nombres que la clave puede usar y
marca los que sirven para este proyecto.
"""
import json
import os
import urllib.error
import urllib.request

from django.core.management.base import BaseCommand

from ai.models import AiSuggestion, AssistantQuery, CareTerm
from ai.providers import gemini_disponible
from communities.models import Community

LISTA_MODELOS = "https://generativelanguage.googleapis.com/v1beta/models"


class Command(BaseCommand):
    help = "Muestra el estado de la capa de IA y ayuda a configurarla."

    def add_arguments(self, parser):
        parser.add_argument(
            "--modelos", action="store_true",
            help="Lista los modelos que acepta la clave configurada.",
        )
        parser.add_argument(
            "--probar", metavar="PREGUNTA",
            help="Hace una consulta real al asistente y muestra la respuesta.",
        )

    def handle(self, *args, **options):
        self._estado()
        if options["modelos"]:
            self.stdout.write("")
            self._modelos()
        if options["probar"]:
            self.stdout.write("")
            self._probar(options["probar"])

    # ------------------------------------------------------------------
    def _estado(self):
        self.stdout.write(self.style.MIGRATE_HEADING("Configuración"))
        clave = os.getenv("GEMINI_API_KEY", "").strip()
        modelo = os.getenv("GEMINI_MODEL", "").strip()
        self.stdout.write(
            f"  GEMINI_API_KEY  {'definida (' + clave[:6] + '…)' if clave else 'SIN DEFINIR'}"
        )
        self.stdout.write(f"  GEMINI_MODEL    {modelo or 'SIN DEFINIR'}")

        disponible, motivo = gemini_disponible()
        if disponible:
            self.stdout.write(self.style.SUCCESS("  → el proveedor externo está listo"))
        else:
            self.stdout.write(
                self.style.WARNING(f"  → proveedor externo apagado: {motivo}")
            )
            self.stdout.write(
                "    El revisor de cuidado cultural funciona igual, con reglas."
            )

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Datos"))
        self.stdout.write(f"  términos de cuidado cultural  {CareTerm.objects.filter(is_active=True).count()}")
        self.stdout.write(f"  sugerencias guardadas         {AiSuggestion.objects.count()}")
        self.stdout.write(f"  consultas al asistente        {AssistantQuery.objects.count()}")

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Qué activó cada comunidad"))
        for community in Community.objects.all():
            ajustes = community.ai_settings or {}
            activas = [k for k, v in ajustes.items() if v] or ["ninguna"]
            self.stdout.write(f"  {community.name:<16} {', '.join(activas)}")

    # ------------------------------------------------------------------
    def _modelos(self):
        self.stdout.write(self.style.MIGRATE_HEADING("Modelos que acepta su clave"))
        clave = os.getenv("GEMINI_API_KEY", "").strip()
        if not clave:
            self.stdout.write(
                self.style.ERROR(
                    "  Defina GEMINI_API_KEY primero (ver docs/DESPLIEGUE.md)."
                )
            )
            return

        peticion = urllib.request.Request(
            LISTA_MODELOS, headers={"x-goog-api-key": clave}
        )
        try:
            with urllib.request.urlopen(peticion, timeout=20) as respuesta:
                datos = json.loads(respuesta.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            self.stdout.write(
                self.style.ERROR(f"  Google respondió {exc.code}: {exc.reason}")
            )
            self.stdout.write("  Revise que la clave sea correcta y esté activa.")
            return
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"  No se pudo consultar: {exc}"))
            return

        utiles = []
        for modelo in datos.get("models", []):
            nombre = modelo.get("name", "").removeprefix("models/")
            metodos = modelo.get("supportedGenerationMethods", [])
            if "generateContent" not in metodos:
                continue
            utiles.append(nombre)
            self.stdout.write(f"  {nombre}")

        if not utiles:
            self.stdout.write(self.style.WARNING("  Ninguno sirve para generar texto."))
            return

        # Orden de preferencia para este proyecto. Google recomienda Gemini 4
        # Hydrogen o 3.5 Flash-Lite para proyectos nuevos; los 2.5 están
        # restringidos a quienes ya los usaban.
        preferidos = [
            "gemini-4-hydrogen",
            "gemini-3.5-flash-lite",
            "gemini-3.8-flash",
            "gemini-3.6-flash",
            "gemini-3.1-flash-lite",
        ]
        sugerido = next(
            (m for m in preferidos if m in utiles),
            next((m for m in utiles if "preview" not in m and "tts" not in m), utiles[0]),
        )
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"  Para este proyecto:  GEMINI_MODEL={sugerido}")
        )
        self.stdout.write(
            "  Si la cuota se queda corta, gemini-3.5-flash-lite es más barato."
        )

    # ------------------------------------------------------------------
    def _probar(self, pregunta):
        from ai.assistant import preguntar

        self.stdout.write(self.style.MIGRATE_HEADING(f"Pregunta: {pregunta}"))
        resultado = preguntar(pregunta)
        self.stdout.write(f"  estado: {resultado['estado']}")
        self.stdout.write("")
        for linea in resultado["respuesta"].splitlines():
            self.stdout.write(f"  {linea}")
        if resultado.get("fuentes"):
            self.stdout.write("")
            self.stdout.write("  Fuentes citadas:")
            for fuente in resultado["fuentes"]:
                self.stdout.write(f"    [{fuente['numero']}] {fuente['titulo']}")
