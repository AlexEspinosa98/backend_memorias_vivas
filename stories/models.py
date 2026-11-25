"""
El muro de Memorias Vivas.

Reglas que vienen del documento base del archivo y que están codificadas aquí:

1. Nada se publica sin autorización: una historia solo pasa a `PUBLISHED`
   cuando tiene al menos un registro de `Consent` (ver `Story.clean`).
2. El acceso lo decide quien publica: `Visibility` distingue contenido de uso
   abierto, contenido para personas registradas, contenido solo para la
   comunidad y contenido restringido con permiso nominal.
3. Los saberes reservados no se mapean: si `is_sensitive` está activo, la
   ubicación exacta no se expone (ver `Story.public_location`).
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

from communities.models import Community


class Visibility(models.TextChoices):
    PUBLIC = "publico", "Uso abierto (visible sin iniciar sesión)"
    REGISTERED = "registrado", "Solo personas registradas"
    COMMUNITY = "comunidad", "Solo la comunidad"
    RESTRICTED = "restringido", "Restringido (permiso nominal)"


class StoryKind(models.TextChoices):
    RELATO = "relato", "Relato"
    TESTIMONIO = "testimonio", "Testimonio"
    MEMORIA = "memoria", "Memoria familiar o comunitaria"
    SABER = "saber", "Saber o práctica"
    LENGUA = "lengua", "Lengua Ika"
    VISITA = "visita", "Visita o recorrido"
    EVENTO = "evento", "Evento o convocatoria"
    PROMOCION = "promocion", "Promoción (artesanía, servicio, iniciativa)"
    AVISO = "aviso", "Aviso de la comunidad"


class StoryStatus(models.TextChoices):
    DRAFT = "borrador", "Borrador"
    IN_REVIEW = "en_revision", "En revisión de la comunidad"
    PUBLISHED = "publicado", "Publicado"
    ARCHIVED = "archivado", "Archivado"
    REJECTED = "rechazado", "No autorizado"


class Tag(models.Model):
    name = models.CharField("nombre", max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True, blank=True)

    class Meta:
        verbose_name = "etiqueta"
        verbose_name_plural = "etiquetas"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:70]
        return super().save(*args, **kwargs)


class StoryQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=StoryStatus.PUBLISHED)

    def visible_for(self, user):
        """
        Filtra el muro según quién mira.

        - Anónimo: solo `PUBLIC`.
        - Registrado: `PUBLIC` + `REGISTERED` + lo de sus comunidades +
          lo restringido que le fue concedido + lo propio.
        - Moderador/admin de plataforma: todo lo publicado (más sus borradores).
        """
        qs = self.published()
        if not user or not user.is_authenticated:
            return qs.filter(visibility=Visibility.PUBLIC)

        if user.is_staff_role:
            return self.filter(
                Q(status=StoryStatus.PUBLISHED) | Q(author=user)
            )

        community_ids = user.community_ids()
        allowed = (
            Q(visibility__in=[Visibility.PUBLIC, Visibility.REGISTERED])
            | Q(visibility=Visibility.COMMUNITY, community_id__in=community_ids)
            | Q(visibility=Visibility.RESTRICTED, access_grants__user=user)
            | Q(author=user)
        )
        return qs.filter(allowed).distinct()

    def editable_by(self, user):
        """Historias que la persona puede modificar (propias o de su comunidad si es autoridad)."""
        if not user or not user.is_authenticated:
            return self.none()
        if user.is_staff_role:
            return self
        return self.filter(
            Q(author=user) | Q(community_id__in=user.authority_community_ids())
        ).distinct()


class Story(models.Model):
    """Una publicación del muro: relato, memoria, visita, promoción o aviso."""

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stories"
    )
    community = models.ForeignKey(
        Community,
        on_delete=models.PROTECT,
        related_name="stories",
        null=True,
        blank=True,
        help_text="Comunidad a la que pertenece el contenido. Obligatoria si la visibilidad es 'comunidad'.",
    )
    kind = models.CharField(
        "tipo", max_length=20, choices=StoryKind.choices, default=StoryKind.RELATO
    )
    title = models.CharField("título", max_length=200)
    summary = models.CharField("resumen", max_length=300, blank=True)
    body = models.TextField("contenido", blank=True)
    language = models.CharField(
        "lengua", max_length=20,
        choices=[("es", "Español"), ("iku", "Ika (Iku)"), ("bilingue", "Bilingüe")],
        default="es",
    )

    visibility = models.CharField(
        "visibilidad", max_length=20, choices=Visibility.choices,
        default=Visibility.COMMUNITY,
    )
    status = models.CharField(
        "estado", max_length=20, choices=StoryStatus.choices, default=StoryStatus.DRAFT
    )

    # Ubicación general del contenido (nunca sitios sagrados reservados).
    place_name = models.CharField("lugar", max_length=200, blank=True)
    latitude = models.DecimalField(
        "latitud", max_digits=9, decimal_places=6, blank=True, null=True
    )
    longitude = models.DecimalField(
        "longitud", max_digits=9, decimal_places=6, blank=True, null=True
    )

    is_sensitive = models.BooleanField(
        "contenido sensible", default=False,
        help_text="Saber colectivo, reservado o con ubicación que no debe divulgarse. "
                  "Oculta la ubicación exacta y exige visibilidad restringida o de comunidad.",
    )
    allow_comments = models.BooleanField("permite comentarios", default=True)
    is_featured = models.BooleanField("destacado en el muro", default=False)

    tags = models.ManyToManyField(Tag, blank=True, related_name="stories")

    # Contadores desnormalizados: el muro los lee en cada carga.
    like_count = models.PositiveIntegerField(default=0, editable=False)
    comment_count = models.PositiveIntegerField(default=0, editable=False)
    view_count = models.PositiveIntegerField(default=0, editable=False)

    review_note = models.TextField(
        "nota de revisión", blank=True,
        help_text="Observación de la autoridad o moderación sobre la publicación.",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_stories",
    )
    published_at = models.DateTimeField("publicado el", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = StoryQuerySet.as_manager()

    class Meta:
        verbose_name = "historia"
        verbose_name_plural = "historias"
        ordering = ["-is_featured", "-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "visibility"]),
            models.Index(fields=["-published_at"]),
            models.Index(fields=["community", "status"]),
        ]

    def __str__(self):
        return self.title

    # --- Reglas de cuidado cultural -------------------------------------
    def clean(self):
        errors = {}
        if self.visibility == Visibility.COMMUNITY and not self.community_id:
            errors["community"] = "Una historia de la comunidad debe indicar cuál."
        if self.is_sensitive and self.visibility in {
            Visibility.PUBLIC,
            Visibility.REGISTERED,
        }:
            errors["visibility"] = (
                "El contenido marcado como sensible no puede ser de uso abierto: "
                "use visibilidad de comunidad o restringida."
            )
        if self.status == StoryStatus.PUBLISHED and not self._has_consent():
            errors["status"] = (
                "No se puede publicar sin al menos un registro de autorización "
                "de la comunidad (Consent)."
            )
        if errors:
            raise ValidationError(errors)

    def _has_consent(self) -> bool:
        return bool(self.pk) and self.consents.exists()

    def publish(self, by=None, note: str = ""):
        """Pasa la historia a publicada; falla si no hay autorización registrada."""
        if not self._has_consent():
            raise ValidationError(
                "Falta el registro de autorización de la comunidad para publicar."
            )
        self.status = StoryStatus.PUBLISHED
        self.published_at = self.published_at or timezone.now()
        self.reviewed_by = by
        if note:
            self.review_note = note
        self.full_clean()
        self.save()
        return self

    @property
    def public_location(self) -> dict | None:
        """Ubicación tal como puede mostrarse: sin coordenadas si es sensible."""
        if not self.place_name and self.latitude is None:
            return None
        if self.is_sensitive:
            return {"place_name": self.place_name or "Ubicación reservada", "approximate": True}
        return {
            "place_name": self.place_name,
            "latitude": float(self.latitude) if self.latitude is not None else None,
            "longitude": float(self.longitude) if self.longitude is not None else None,
            "approximate": False,
        }

    def can_be_seen_by(self, user) -> bool:
        if self.status != StoryStatus.PUBLISHED:
            return bool(
                user
                and user.is_authenticated
                and (user == self.author or user.is_staff_role
                     or self.community_id in user.authority_community_ids())
            )
        if self.visibility == Visibility.PUBLIC:
            return True
        if not user or not user.is_authenticated:
            return False
        if user.is_staff_role or user == self.author:
            return True
        if self.visibility == Visibility.REGISTERED:
            return True
        if self.visibility == Visibility.COMMUNITY:
            return self.community_id in user.community_ids()
        return self.access_grants.filter(user=user).exists()

    def recount(self):
        """
        Recalcula los contadores desde las tablas reales.

        Se consulta por `story_id` y no por el related manager: si la instancia
        viene de un `prefetch_related`, el manager devolvería el conteo cacheado
        de antes del cambio.
        """
        Story.objects.filter(pk=self.pk).update(
            like_count=Reaction.objects.filter(story_id=self.pk).count(),
            comment_count=Comment.objects.filter(
                story_id=self.pk, is_hidden=False
            ).count(),
        )


class MediaItem(models.Model):
    """Foto, audio o video adjunto a una historia, con sus créditos."""

    class Kind(models.TextChoices):
        IMAGE = "imagen", "Imagen"
        AUDIO = "audio", "Audio"
        VIDEO = "video", "Video"
        DOCUMENT = "documento", "Documento"

    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="media")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.IMAGE)
    file = models.FileField("archivo", upload_to="stories/%Y/%m/", blank=True, null=True)
    external_url = models.URLField(
        "enlace externo", blank=True,
        help_text="Para materiales ya publicados por terceros (video, documental).",
    )
    caption = models.CharField("descripción", max_length=300, blank=True)
    credit = models.CharField(
        "crédito", max_length=300, blank=True,
        help_text="Autoría y fuente, como exige la nota metodológica del archivo.",
    )
    transcript = models.TextField(
        "transcripción", blank=True,
        help_text="Transcripción revisada por la comunidad. No se publica sin revisión.",
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "material"
        verbose_name_plural = "materiales"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.get_kind_display()} · {self.story.title}"


class Consent(models.Model):
    """
    Registro de la autorización comunitaria sobre un contenido.

    Sin al menos uno de estos registros la historia no puede publicarse.
    """

    class Scope(models.TextChoices):
        OPEN = "abierto", "Divulgación abierta"
        COMMUNITY = "comunidad", "Solo dentro de la comunidad"
        RESEARCH = "consulta", "Solo consulta interna / investigación autorizada"

    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="consents")
    granted_by_name = models.CharField("autoriza", max_length=160)
    granted_by_role = models.CharField(
        "calidad en que autoriza", max_length=160, blank=True,
        help_text="Por ejemplo: Mamo, Cabildo Gobernador, autoridad de la comunidad, la persona del relato.",
    )
    community = models.ForeignKey(
        Community, on_delete=models.PROTECT, null=True, blank=True,
        related_name="consents",
    )
    scope = models.CharField(max_length=20, choices=Scope.choices, default=Scope.COMMUNITY)
    granted_on = models.DateField("fecha de autorización", default=timezone.localdate)
    conditions = models.TextField(
        "condiciones de uso", blank=True,
        help_text="Restricciones indicadas por la comunidad (no reproducir audio, no mapear, etc.).",
    )
    evidence = models.FileField(
        "soporte", upload_to="consents/%Y/", blank=True, null=True,
        help_text="Acta, audio o documento de la autorización.",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="recorded_consents",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "autorización"
        verbose_name_plural = "autorizaciones"
        ordering = ["-granted_on"]

    def __str__(self):
        return f"{self.granted_by_name} ({self.granted_on})"


class StoryAccessGrant(models.Model):
    """Permiso nominal para ver una historia restringida."""

    story = models.ForeignKey(
        Story, on_delete=models.CASCADE, related_name="access_grants"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="story_grants"
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="granted_story_access",
    )
    reason = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "permiso de acceso"
        verbose_name_plural = "permisos de acceso"
        constraints = [
            models.UniqueConstraint(fields=["story", "user"], name="unique_story_grant")
        ]

    def __str__(self):
        return f"{self.user} → {self.story}"


class Reaction(models.Model):
    """Un 'me gusta' o reconocimiento sobre una historia."""

    class Kind(models.TextChoices):
        LIKE = "aprecio", "Aprecio"
        THANKS = "gratitud", "Gratitud"
        IMPORTANT = "importante", "Importante"

    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reactions"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.LIKE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "reacción"
        verbose_name_plural = "reacciones"
        constraints = [
            models.UniqueConstraint(fields=["story", "user"], name="unique_reaction")
        ]

    def __str__(self):
        return f"{self.user} · {self.get_kind_display()}"


class Comment(models.Model):
    """Comentario en una historia. Admite un nivel de respuesta."""

    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    body = models.TextField("comentario")
    is_hidden = models.BooleanField(
        "oculto por moderación", default=False
    )
    hidden_reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "comentario"
        verbose_name_plural = "comentarios"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.author}: {self.body[:40]}"


class Visit(models.Model):
    """
    Registro de una visita o recorrido al territorio.

    Se publica como historia de tipo `visita`; aquí van los datos propios
    (fechas, cupo, condiciones) para que la comunidad las administre.
    """

    story = models.OneToOneField(
        Story, on_delete=models.CASCADE, related_name="visit"
    )
    starts_on = models.DateField("inicia")
    ends_on = models.DateField("termina", null=True, blank=True)
    meeting_point = models.CharField("punto de encuentro", max_length=200, blank=True)
    capacity = models.PositiveSmallIntegerField("cupo", null=True, blank=True)
    contact = models.CharField("contacto", max_length=160, blank=True)
    conditions = models.TextField(
        "condiciones de la comunidad", blank=True,
        help_text="Acuerdos de respeto, lugares a los que no se entra, aportes.",
    )

    class Meta:
        verbose_name = "visita"
        verbose_name_plural = "visitas"
        ordering = ["starts_on"]

    def __str__(self):
        return f"Visita · {self.story.title}"


class Promotion(models.Model):
    """Iniciativa que una persona o comunidad promociona en el muro."""

    class Category(models.TextChoices):
        ARTESANIA = "artesania", "Artesanía y tejido"
        AGRICULTURA = "agricultura", "Producto agrícola"
        TURISMO = "turismo", "Turismo comunitario"
        TALLER = "taller", "Taller o formación"
        OTRO = "otro", "Otra iniciativa"

    story = models.OneToOneField(
        Story, on_delete=models.CASCADE, related_name="promotion"
    )
    category = models.CharField(max_length=20, choices=Category.choices)
    contact = models.CharField("contacto", max_length=160, blank=True)
    link = models.URLField("enlace", blank=True)
    price_note = models.CharField(
        "nota de precio", max_length=160, blank=True,
        help_text="Texto libre: la plataforma no procesa pagos.",
    )
    active_until = models.DateField("vigente hasta", null=True, blank=True)

    class Meta:
        verbose_name = "promoción"
        verbose_name_plural = "promociones"

    def __str__(self):
        return f"Promoción · {self.story.title}"


class Report(models.Model):
    """Reporte de un contenido que puede afectar el cuidado cultural."""

    class Reason(models.TextChoices):
        NO_CONSENT = "sin_autorizacion", "Publicado sin autorización"
        SENSITIVE = "saber_reservado", "Expone un saber reservado"
        SACRED = "sitio_sagrado", "Expone un sitio sagrado"
        WRONG = "informacion_erronea", "Información incorrecta"
        ABUSE = "ofensivo", "Contenido ofensivo"
        OTHER = "otro", "Otro"

    class Status(models.TextChoices):
        OPEN = "abierto", "Abierto"
        REVIEWING = "en_revision", "En revisión"
        RESOLVED = "resuelto", "Resuelto"
        DISMISSED = "descartado", "Descartado"

    story = models.ForeignKey(
        Story, on_delete=models.CASCADE, related_name="reports", null=True, blank=True
    )
    comment = models.ForeignKey(
        Comment, on_delete=models.CASCADE, related_name="reports", null=True, blank=True
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="reports",
    )
    reason = models.CharField(max_length=30, choices=Reason.choices)
    detail = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    resolution = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "reporte"
        verbose_name_plural = "reportes"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_reason_display()} ({self.get_status_display()})"
