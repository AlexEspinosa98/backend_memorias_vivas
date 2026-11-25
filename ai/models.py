"""
Modelos de la capa de inteligencia artificial.

Tres piezas, y ninguna escribe sobre el contenido del archivo:

- `CareTerm`  — la lista de términos y lugares que exigen revisión de
  autoridad. La define la comunidad, se edita desde el admin y **no se
  publica**: es, en sí misma, información sensible.
- `AiSuggestion` — toda salida de IA vive aquí, en estado `pendiente`, hasta
  que una persona la acepta o la descarta. Nunca se escribe directo sobre
  `Story.body`, `Story.tags` ni `MediaItem.transcript`.
- `AiAuditLog` — qué función corrió, con qué proveedor, sobre qué contenido y
  a pedido de quién. Es lo que permite responderle a una comunidad qué hizo
  el sistema con sus materiales.
"""
from django.conf import settings
from django.db import models

from communities.models import Community
from stories.models import Story


class CareTerm(models.Model):
    """Término que, si aparece en un borrador, exige mirada de autoridad."""

    class Kind(models.TextChoices):
        PLACE = "lugar", "Lugar que puede ser sagrado"
        PRACTICE = "practica", "Práctica ceremonial"
        KNOWLEDGE = "saber", "Saber reservado"
        PERSON = "persona", "Voz atribuible a una persona"
        OTHER = "otro", "Otro"

    term = models.CharField("término", max_length=120)
    kind = models.CharField("tipo", max_length=20, choices=Kind.choices)
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="care_terms",
        help_text="Déjelo vacío si aplica a todas las comunidades.",
    )
    note = models.CharField(
        "por qué", max_length=300, blank=True,
        help_text="Qué debe verificar la autoridad cuando aparezca.",
    )
    is_active = models.BooleanField("activo", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "término de cuidado cultural"
        verbose_name_plural = "términos de cuidado cultural"
        ordering = ["kind", "term"]
        constraints = [
            models.UniqueConstraint(
                fields=["term", "community"], name="unique_care_term"
            )
        ]

    def __str__(self):
        return f"{self.term} ({self.get_kind_display()})"


class AiSuggestion(models.Model):
    """Una salida de IA esperando decisión humana."""

    class Kind(models.TextChoices):
        CARE_REVIEW = "revision_cuidado", "Revisión de cuidado cultural"
        TRANSCRIPT = "transcripcion", "Transcripción de audio"
        TAGS = "etiquetas", "Etiquetas sugeridas"
        SUMMARY = "resumen", "Resumen sugerido"

    class Status(models.TextChoices):
        PENDING = "pendiente", "Pendiente"
        ACCEPTED = "aceptada", "Aceptada"
        DISMISSED = "descartada", "Descartada"

    story = models.ForeignKey(
        Story, on_delete=models.CASCADE, related_name="ai_suggestions"
    )
    kind = models.CharField(max_length=30, choices=Kind.choices)
    payload = models.JSONField("contenido", default=dict)
    provider = models.CharField(
        "proveedor", max_length=40, default="reglas",
        help_text="`reglas` cuando no intervino ningún modelo.",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ai_decisions",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "sugerencia de IA"
        verbose_name_plural = "sugerencias de IA"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["story", "kind", "status"])]

    def __str__(self):
        return f"{self.get_kind_display()} · {self.story}"

    @property
    def findings(self) -> list[dict]:
        """Hallazgos de una revisión de cuidado cultural."""
        return self.payload.get("hallazgos", [])


class AssistantQuery(models.Model):
    """
    Cada consulta al asistente, con lo que respondió.

    Queda registrada para que la comunidad pueda auditar qué está diciendo el
    sistema en su nombre, y para ver qué le preguntan al archivo.
    """

    class Status(models.TextChoices):
        ANSWERED = "respondida", "Respondida"
        REFUSED = "vedada", "Tema que no se responde"
        NO_DATA = "sin_datos", "No está en el archivo"

    question = models.TextField("pregunta")
    answer = models.TextField("respuesta", blank=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    blocked_by = models.CharField(
        "término que la bloqueó", max_length=120, blank=True
    )
    sources = models.JSONField("fuentes citadas", default=list, blank=True)
    provider = models.CharField(max_length=40, default="reglas")
    asked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assistant_queries",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "consulta al asistente"
        verbose_name_plural = "consultas al asistente"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.question[:60]} ({self.get_status_display()})"


class AiAuditLog(models.Model):
    """Registro de cada vez que la IA toca un contenido."""

    story = models.ForeignKey(
        Story, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ai_logs",
    )
    function = models.CharField("función", max_length=40)
    provider = models.CharField("proveedor", max_length=40)
    outcome = models.CharField("resultado", max_length=200, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ai_requests",
    )
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "registro de IA"
        verbose_name_plural = "registros de IA"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.function} · {self.provider} · {self.created_at:%Y-%m-%d %H:%M}"
