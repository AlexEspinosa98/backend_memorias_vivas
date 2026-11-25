"""
Proveedores del revisor de cuidado cultural.

Dos, y el primero basta para que la función sirva:

- `reglas` — la lista de términos que la comunidad mantiene. Corre en el
  servidor, no necesita GPU ni clave, y **nada sale de aquí**.
- `gemini` — una segunda mirada con un modelo de lenguaje, opcional y
  desactivada por defecto. Solo corre si la comunidad lo autorizó
  explícitamente (`guards.sends_content_outside`) y si hay clave y modelo
  configurados.

El nombre del modelo NO trae valor por defecto a propósito: los nombres de
los modelos de Gemini cambian seguido y uno equivocado fallaría en silencio.
Cópielo de Google AI Studio y póngalo en `GEMINI_MODEL`. Sin esa variable el
proveedor queda apagado y el revisor funciona igual con reglas.
"""
from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

INSTRUCCIONES = """Eres un apoyo para las autoridades de un archivo comunitario del pueblo Arhuaco (Iku).
No decides nada: solo señalas lo que una autoridad debería verificar antes de publicar.

Lee el texto y responde ÚNICAMENTE con un JSON de esta forma:
{"hallazgos": [{"tipo": "lugar|practica|saber|persona", "fragmento": "...", "por_que": "..."}]}

Señala un hallazgo solo si el texto:
- menciona un lugar que podría ser sagrado o de pagamento;
- describe una práctica ceremonial;
- atribuye palabras o conocimientos a una persona identificable.

Si no encuentras nada, responde {"hallazgos": []}.
No expliques, no saludes, no agregues texto fuera del JSON.
No juzgues el valor del contenido ni propongas cómo reescribirlo."""


def _sin_tildes(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(c) != "Mn"
    )


def buscar_terminos(texto: str, terms) -> list[dict]:
    """
    Proveedor `reglas`: busca los términos de la comunidad en el texto.

    Compara sin tildes y sin mayúsculas, y exige límite de palabra para que
    «era» no dispare dentro de «generación».
    """
    plano = _sin_tildes(texto)
    hallazgos: list[dict] = []
    for term in terms:
        aguja = _sin_tildes(term.term).strip()
        if not aguja:
            continue
        if re.search(rf"(?<!\w){re.escape(aguja)}(?!\w)", plano):
            hallazgos.append(
                {
                    "tipo": term.kind,
                    "fragmento": term.term,
                    "por_que": term.note
                    or "Está en la lista de términos que la comunidad pidió revisar.",
                    "origen": "reglas",
                }
            )
    return hallazgos


def gemini_disponible() -> tuple[bool, str]:
    """¿Está configurado el proveedor externo? Devuelve (sí/no, motivo)."""
    if not os.getenv("GEMINI_API_KEY", "").strip():
        return False, "falta GEMINI_API_KEY"
    if not os.getenv("GEMINI_MODEL", "").strip():
        return False, "falta GEMINI_MODEL (cópielo de Google AI Studio)"
    return True, ""


def _llamar_gemini(
    instrucciones: str, mensaje: str, *, json_mode: bool, timeout: int
) -> dict | None:
    """Una llamada al modelo. Devuelve el JSON crudo, o None si algo falló."""
    ok, motivo = gemini_disponible()
    if not ok:
        logger.info("Gemini no configurado: %s", motivo)
        return None

    config: dict = {"temperature": 0}
    if json_mode:
        config["responseMimeType"] = "application/json"

    cuerpo = json.dumps(
        {
            "systemInstruction": {"parts": [{"text": instrucciones}]},
            "contents": [{"role": "user", "parts": [{"text": mensaje}]}],
            "generationConfig": config,
        }
    ).encode("utf-8")

    peticion = urllib.request.Request(
        GEMINI_ENDPOINT.format(model=os.environ["GEMINI_MODEL"].strip()),
        data=cuerpo,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": os.environ["GEMINI_API_KEY"].strip(),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
            return json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        logger.warning("Gemini respondió %s: %s", exc.code, exc.reason)
    except Exception as exc:  # red caída, timeout, JSON inválido
        logger.warning("Gemini no respondió: %s", exc)
    return None


def _texto_de(datos: dict) -> str:
    try:
        return datos["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        logger.warning("Respuesta de Gemini con forma inesperada")
        return ""


def preguntar_a_gemini(instrucciones: str, mensaje: str, *, timeout: int = 30) -> str:
    """
    Una respuesta en texto para el asistente de consulta.

    Devuelve cadena vacía si el proveedor no está configurado o falla: el
    asistente responde entonces que no puede, en lugar de inventar.
    """
    datos = _llamar_gemini(
        instrucciones, mensaje, json_mode=False, timeout=timeout
    )
    return _texto_de(datos).strip() if datos else ""


def analizar_con_gemini(texto: str, *, timeout: int = 20) -> list[dict]:
    """
    Proveedor `gemini`: segunda mirada con un modelo de lenguaje.

    Devuelve la lista de hallazgos, o una lista vacía si algo falla. Nunca
    lanza: el revisor debe seguir funcionando con reglas aunque el proveedor
    externo esté caído, mal configurado o sin cuota.
    """
    datos = _llamar_gemini(INSTRUCCIONES, texto, json_mode=True, timeout=timeout)
    if datos is None:
        return []
    try:
        hallazgos = json.loads(_texto_de(datos)).get("hallazgos", [])
    except (ValueError, AttributeError) as exc:
        logger.warning("Gemini no devolvió el JSON esperado: %s", exc)
        return []

    limpios = []
    for h in hallazgos[:10]:
        if not isinstance(h, dict):
            continue
        limpios.append(
            {
                "tipo": str(h.get("tipo", "otro"))[:20],
                "fragmento": str(h.get("fragmento", ""))[:200],
                "por_que": str(h.get("por_que", ""))[:300],
                "origen": "gemini",
            }
        )
    return limpios
