"""
Revisor de cuidado cultural.

Corre cuando una historia se envía a revisión y deja una nota para la
autoridad que la va a mirar. No bloquea nada: marca y explica.

El riesgo real del archivo no es técnico. Es que alguien publique de buena fe
algo que no debía salir: un sitio sagrado nombrado al pasar, una práctica de
pagamento descrita, la voz de un mayor que no dio permiso. Esta función
existe para que esa persona lo note antes, no para decidir por ella.
"""
from __future__ import annotations

import logging

from .guards import CareRuleViolation, community_allows, may_process, record
from .models import AiAuditLog, AiSuggestion, CareTerm
from .providers import analizar_con_gemini, buscar_terminos

logger = logging.getLogger(__name__)

FEATURE = "revisor_cuidado"


def _texto_de(story) -> str:
    partes = [story.title, story.summary, story.body, story.place_name]
    return "\n".join(p for p in partes if p)


def _terminos_para(story):
    """Los de su comunidad más los que aplican a todas."""
    from django.db.models import Q

    return CareTerm.objects.filter(is_active=True).filter(
        Q(community__isnull=True) | Q(community_id=story.community_id)
    )


def revisar(story, *, user=None) -> AiSuggestion | None:
    """
    Revisa una historia y guarda la nota como sugerencia pendiente.

    Devuelve la sugerencia, o `None` si la comunidad no activó la función.
    Nunca lanza: un fallo del revisor no puede impedir que una persona envíe
    su historia a revisión.
    """
    try:
        may_process(story, FEATURE)
    except CareRuleViolation as exc:
        logger.info("Revisor no corre sobre «%s»: %s", story.title, exc)
        return None

    texto = _texto_de(story)
    hallazgos = buscar_terminos(texto, _terminos_para(story))
    proveedor = "reglas"

    # Segunda mirada con un modelo, solo si la comunidad lo autorizó.
    try:
        may_process(story, FEATURE, external=True)
    except CareRuleViolation as exc:
        logger.debug("Sin proveedor externo para «%s»: %s", story.title, exc)
    else:
        externos = analizar_con_gemini(texto)
        if externos:
            hallazgos = hallazgos + externos
            proveedor = "reglas+gemini"
        else:
            proveedor = "reglas+gemini"

    payload = {
        "hallazgos": hallazgos,
        "resumen": _resumen(hallazgos),
    }
    return record(
        story, kind=AiSuggestion.Kind.CARE_REVIEW, payload=payload,
        provider=proveedor, user=user,
    )


def _resumen(hallazgos: list[dict]) -> str:
    if not hallazgos:
        return (
            "No se encontró nada que señalar. Esto no reemplaza su lectura: "
            "el revisor solo busca lo que la comunidad le enseñó a buscar."
        )
    tipos = {h.get("tipo") for h in hallazgos}
    nombres = {
        "lugar": "un lugar que podría ser sagrado",
        "practica": "una práctica ceremonial",
        "saber": "un saber reservado",
        "persona": "palabras atribuidas a una persona identificable",
    }
    legibles = [nombres.get(t, "algo que conviene revisar") for t in sorted(tipos)]
    if len(legibles) == 1:
        lista = legibles[0]
    else:
        lista = ", ".join(legibles[:-1]) + " y " + legibles[-1]
    return (
        f"Este texto menciona {lista}. Conviene verificarlo con la autoridad "
        f"correspondiente antes de publicar."
    )


def ultima_revision(story) -> AiSuggestion | None:
    return (
        AiSuggestion.objects.filter(
            story=story, kind=AiSuggestion.Kind.CARE_REVIEW
        )
        .order_by("-created_at")
        .first()
    )


def esta_activo(community) -> bool:
    return community_allows(community, FEATURE)


__all__ = [
    "FEATURE",
    "revisar",
    "ultima_revision",
    "esta_activo",
    "AiAuditLog",
]
