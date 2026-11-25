"""
Secciones del archivo digital (las 13 del documento base) y sus fuentes.

Esto es el contenido editorial curado: convive con el muro, pero no es el muro.
Siempre es de consulta abierta salvo que se marque lo contrario.
"""
from django.db import models
from django.utils.text import slugify


class ArchiveSection(models.Model):
    number = models.PositiveSmallIntegerField("número", unique=True)
    title = models.CharField("título", max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    lead = models.TextField("entradilla", blank=True)
    body = models.TextField("contenido", blank=True)
    care_note = models.TextField(
        "nota de cuidado cultural", blank=True,
        help_text="Advertencia sobre lo que no se desarrolla en esta sección y por qué.",
    )
    is_published = models.BooleanField("publicada", default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "sección del archivo"
        verbose_name_plural = "secciones del archivo"
        ordering = ["number"]

    def __str__(self):
        return f"{self.number}. {self.title}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:220]
        return super().save(*args, **kwargs)


class Figure(models.Model):
    """Figura de una sección, con su crédito completo (exigencia del documento base)."""

    section = models.ForeignKey(
        ArchiveSection, on_delete=models.CASCADE, related_name="figures"
    )
    number = models.PositiveSmallIntegerField("figura", null=True, blank=True)
    caption = models.CharField("título de la figura", max_length=300)
    note = models.TextField(
        "nota", blank=True, help_text="Crédito, autoría, publicación y año."
    )
    image = models.ImageField(upload_to="archive/", blank=True, null=True)
    external_url = models.URLField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "figura"
        verbose_name_plural = "figuras"
        ordering = ["order", "number", "id"]

    def __str__(self):
        return self.caption


class Source(models.Model):
    """Referencia bibliográfica o audiovisual del archivo."""

    class Kind(models.TextChoices):
        INSTITUTIONAL = "institucional", "Fuente institucional"
        ACADEMIC = "academica", "Fuente académica"
        ORGANIZATION = "organizacion", "Organización indígena"
        AUDIOVISUAL = "audiovisual", "Material audiovisual"
        PHOTO = "fotografica", "Fuente fotográfica"
        NORM = "norma", "Norma o decreto"

    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.INSTITUTIONAL)
    citation = models.TextField("referencia")
    url = models.URLField(blank=True)
    year = models.CharField(max_length=20, blank=True)
    sections = models.ManyToManyField(
        ArchiveSection, blank=True, related_name="sources"
    )

    class Meta:
        verbose_name = "fuente"
        verbose_name_plural = "fuentes"
        ordering = ["kind", "citation"]

    def __str__(self):
        return self.citation[:80]
