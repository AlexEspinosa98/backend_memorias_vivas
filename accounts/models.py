from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Gestor de usuarios con el correo como identificador."""

    use_in_migrations = True

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("El correo es obligatorio")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", User.Role.ADMIN)
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("Un superusuario debe tener is_staff e is_superuser")
        return self._create(email, password, **extra)


class User(AbstractUser):
    """
    Usuario de Memorias Vivas.

    `role` es el rol a nivel de plataforma. El rol dentro de una comunidad
    concreta vive en `communities.Membership` (una persona puede ser miembro
    de una comunidad y visitante en otra).
    """

    class Role(models.TextChoices):
        VISITOR = "visitante", "Visitante"
        MEMBER = "miembro", "Miembro de comunidad"
        AUTHORITY = "autoridad", "Autoridad tradicional"
        MODERATOR = "moderador", "Moderador"
        ADMIN = "admin", "Administrador"

    username = None
    email = models.EmailField("correo", unique=True)
    display_name = models.CharField("nombre visible", max_length=120)
    role = models.CharField(
        "rol en la plataforma", max_length=20, choices=Role.choices, default=Role.VISITOR
    )
    bio = models.TextField("presentación", blank=True)
    avatar = models.ImageField("foto", upload_to="avatars/", blank=True, null=True)
    place = models.CharField("lugar", max_length=160, blank=True)
    # Aceptación explícita de los criterios de cuidado cultural del archivo.
    accepted_care_terms_at = models.DateTimeField(
        "aceptó criterios de cuidado cultural", blank=True, null=True
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]

    objects = UserManager()

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["display_name", "email"]

    def __str__(self):
        return self.display_name or self.email

    def save(self, *args, **kwargs):
        if not self.display_name:
            self.display_name = self.email.split("@")[0]
        return super().save(*args, **kwargs)

    # --- Ayudas de autorización -----------------------------------------
    @property
    def is_staff_role(self) -> bool:
        """Modera o administra toda la plataforma."""
        return self.role in {self.Role.MODERATOR, self.Role.ADMIN} or self.is_superuser

    def community_ids(self) -> list[int]:
        """Comunidades donde la persona es miembro activo."""
        return list(
            self.memberships.filter(status="activo").values_list(
                "community_id", flat=True
            )
        )

    def authority_community_ids(self) -> list[int]:
        """Comunidades donde la persona es autoridad o moderadora."""
        return list(
            self.memberships.filter(
                status="activo", role__in=["autoridad", "moderador"]
            ).values_list("community_id", flat=True)
        )
