"""
Las cinco reglas que toda función de IA debe cumplir.

Están aquí, en un solo lugar, para que ninguna función las pueda saltar.
Cualquier módulo nuevo de `ai/` parte de estas funciones y no de
`Story.objects` directamente.

1. Solo contenido autorizado: ningún modelo lee una historia sin `Consent`.
2. El alcance del consentimiento manda.
3. Lo sensible no sale: queda fuera de índices, resúmenes y sugerencias.
4. Nada se publica solo: la IA propone, una persona acepta.
5. Nada sale hacia afuera sin que la comunidad lo haya activado.
"""
from __future__ import annotations

from django.db.models import QuerySet

from stories.models import Consent, Story, Visibility


class CareRuleViolation(Exception):
    """Una función de IA intentó algo que las reglas no permiten."""


# --- Regla 1 y 2: qué contenido puede leer un modelo ---------------------
def authorized_stories() -> QuerySet[Story]:
    """Historias con al menos una autorización registrada."""
    return Story.objects.filter(consents__isnull=False).distinct()


def indexable_stories() -> QuerySet[Story]:
    """
    Lo que puede entrar a un índice o alimentar sugerencias.

    Excluye lo sensible (regla 3) y lo autorizado solo para consulta interna
    (regla 2): un `Consent` de alcance `consulta` no alimenta búsqueda ni
    recomendaciones, por más que la historia esté publicada.
    """
    return (
        authorized_stories()
        .filter(is_sensitive=False)
        .filter(consents__scope__in=[Consent.Scope.OPEN, Consent.Scope.COMMUNITY])
        .distinct()
    )


def visible_index_for(user) -> QuerySet[Story]:
    """
    Lo indexable que ADEMÁS esa persona puede ver.

    El filtro va antes de calcular cualquier similitud, nunca después: si se
    filtra después, los resultados descartados ya revelaron que existen.
    """
    permitidas = Story.objects.visible_for(user).values("pk")
    return indexable_stories().filter(pk__in=permitidas)


# --- Regla 5: la comunidad activa cada función ---------------------------
def community_allows(community, feature: str) -> bool:
    """
    ¿La comunidad activó esta función sobre sus contenidos?

    Por defecto está todo desactivado: `ai_settings` vacío significa que no.
    Una historia sin comunidad no la administra nadie, así que tampoco.
    """
    if community is None:
        return False
    return bool((community.ai_settings or {}).get(feature))


def sends_content_outside(community, feature: str) -> bool:
    """
    ¿Esta comunidad autorizó mandar el texto a un proveedor externo?

    Es una decisión aparte de activar la función: el revisor puede correr con
    reglas locales sin que nada salga del servidor.
    """
    if community is None:
        return False
    settings_ = community.ai_settings or {}
    return bool(settings_.get(f"{feature}_externo"))


def may_process(story: Story, feature: str, *, external: bool = False) -> None:
    """
    Comprueba las reglas antes de que un modelo toque una historia.

    Lanza `CareRuleViolation` con el motivo, en lugar de devolver False: el
    motivo es lo que se registra en la auditoría.
    """
    if not community_allows(story.community, feature):
        raise CareRuleViolation(
            f"La comunidad no ha activado «{feature}» sobre sus contenidos."
        )

    if external:
        if story.is_sensitive:
            raise CareRuleViolation(
                "El contenido sensible no sale del servidor bajo ninguna "
                "circunstancia."
            )
        if story.visibility == Visibility.RESTRICTED:
            raise CareRuleViolation(
                "El contenido de acceso restringido no se envía a un proveedor "
                "externo."
            )
        if not sends_content_outside(story.community, feature):
            raise CareRuleViolation(
                f"La comunidad no autorizó enviar su contenido a un proveedor "
                f"externo para «{feature}»."
            )


# --- Regla 4: la IA propone, no publica ----------------------------------
def record(story, *, kind, payload, provider, user=None):
    """
    Guarda una salida de IA como sugerencia pendiente y la deja en auditoría.

    Es el único camino por el que una salida de IA entra al sistema.
    """
    from .models import AiAuditLog, AiSuggestion

    suggestion, _ = AiSuggestion.objects.update_or_create(
        story=story,
        kind=kind,
        defaults={
            "payload": payload,
            "provider": provider,
            "status": AiSuggestion.Status.PENDING,
            "decided_by": None,
            "decided_at": None,
        },
    )
    AiAuditLog.objects.create(
        story=story,
        function=kind,
        provider=provider,
        outcome=f"{len(payload.get('hallazgos', []))} hallazgo(s)",
        requested_by=user,
        detail={"visibility": story.visibility, "sensitive": story.is_sensitive},
    )
    return suggestion
