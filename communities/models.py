from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Community(models.Model):
    """
    Una comunidad o asentamiento que participa en el archivo.

    El documento base advierte que no debe presentarse una única estructura
    como idéntica en todos los asentamientos: cada comunidad define su propio
    nombre, autoridades y condiciones de acceso.
    """

    name = models.CharField("nombre", max_length=160, unique=True)
    slug = models.SlugField("slug", max_length=180, unique=True, blank=True)
    people = models.CharField(
        "pueblo", max_length=80, default="Arhuaco (Iku)",
        help_text="Pueblo al que pertenece la comunidad (Arhuaco, Kogui, Wiwa, Kankuamo…).",
    )
    description = models.TextField("descripción", blank=True)
    territory = models.CharField(
        "territorio / resguardo", max_length=200, blank=True,
        help_text="Zona de asentamiento, cuenca o resguardo, como la nombre la comunidad.",
    )
    municipality = models.CharField("municipio", max_length=120, blank=True)
    department = models.CharField("departamento", max_length=120, blank=True)
    # Ubicación general; nunca sitios sagrados ni coordenadas reservadas.
    latitude = models.DecimalField(
        "latitud", max_digits=9, decimal_places=6, blank=True, null=True
    )
    longitude = models.DecimalField(
        "longitud", max_digits=9, decimal_places=6, blank=True, null=True
    )
    cover = models.ImageField("imagen", upload_to="communities/", blank=True, null=True)
    is_open_to_requests = models.BooleanField(
        "acepta solicitudes de ingreso", default=True
    )
    ai_settings = models.JSONField(
        "funciones de IA activadas", default=dict, blank=True,
        help_text=(
            "Cada comunidad decide qué funciones de inteligencia artificial "
            "corren sobre sus contenidos. Vacío significa ninguna. "
            'Ejemplo: {"revisor_cuidado": true, "revisor_cuidado_externo": false}. '
            "El sufijo `_externo` autoriza, además, enviar el texto a un "
            "proveedor fuera del servidor."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "comunidad"
        verbose_name_plural = "comunidades"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:180]
        return super().save(*args, **kwargs)

    @property
    def member_count(self):
        return self.memberships.filter(status=Membership.Status.ACTIVE).count()


class Membership(models.Model):
    """Vínculo de una persona con una comunidad, y su rol dentro de ella."""

    class Role(models.TextChoices):
        MEMBER = "miembro", "Miembro"
        AUTHORITY = "autoridad", "Autoridad tradicional"
        MODERATOR = "moderador", "Moderador de la comunidad"

    class Status(models.TextChoices):
        PENDING = "pendiente", "Solicitud pendiente"
        ACTIVE = "activo", "Activo"
        REJECTED = "rechazado", "Rechazado"
        LEFT = "retirado", "Retirado"

    community = models.ForeignKey(
        Community, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    note = models.CharField(
        "nota de la solicitud", max_length=300, blank=True,
        help_text="Por qué pide ingresar, o quién la presenta.",
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="membership_decisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "vínculo con comunidad"
        verbose_name_plural = "vínculos con comunidades"
        constraints = [
            models.UniqueConstraint(
                fields=["community", "user"], name="unique_membership"
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} · {self.community} ({self.get_status_display()})"
