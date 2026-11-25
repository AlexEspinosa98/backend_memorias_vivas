"""
Pruebas de las reglas que protegen el archivo.

Lo que se verifica aquí es, sobre todo, quién puede ver qué y que nada se
publique sin autorización registrada.

    python manage.py test
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from communities.models import Community, Membership
from stories.models import (
    Consent,
    Story,
    StoryAccessGrant,
    StoryKind,
    StoryStatus,
    Visibility,
)

User = get_user_model()


def make_user(email, role="miembro", **extra):
    return User.objects.create_user(
        email=email, password="clave-de-prueba-123", display_name=email.split("@")[0],
        role=role, **extra
    )


def add_consent(story, scope=Consent.Scope.OPEN):
    return Consent.objects.create(
        story=story,
        granted_by_name="Autoridad de prueba",
        granted_by_role="Autoridad de la comunidad",
        community=story.community,
        scope=scope,
        granted_on=date.today(),
    )


class BaseFixture:
    """Dos comunidades, cuatro personas y una historia por nivel de visibilidad."""

    def build(self):
        self.com_a = Community.objects.create(name="Comunidad A")
        self.com_b = Community.objects.create(name="Comunidad B")

        self.autoridad_a = make_user("autoridad_a@test.co", role="autoridad")
        self.miembro_a = make_user("miembro_a@test.co")
        self.miembro_b = make_user("miembro_b@test.co")
        self.registrado = make_user("suelto@test.co", role="visitante")
        self.moderador = make_user("mod@test.co", role="moderador")

        Membership.objects.create(
            community=self.com_a, user=self.autoridad_a,
            role=Membership.Role.AUTHORITY, status=Membership.Status.ACTIVE,
        )
        Membership.objects.create(
            community=self.com_a, user=self.miembro_a, status=Membership.Status.ACTIVE
        )
        Membership.objects.create(
            community=self.com_b, user=self.miembro_b, status=Membership.Status.ACTIVE
        )
        # Solicitud pendiente: no debe dar acceso al contenido de comunidad.
        Membership.objects.create(
            community=self.com_a, user=self.registrado, status=Membership.Status.PENDING
        )

        self.publica = self._story("Pública", Visibility.PUBLIC)
        self.registrada = self._story("Registrada", Visibility.REGISTERED)
        self.de_comunidad = self._story("De comunidad", Visibility.COMMUNITY)
        self.restringida = self._story("Restringida", Visibility.RESTRICTED)

    def _story(self, title, visibility, **extra):
        story = Story.objects.create(
            author=self.miembro_a,
            community=self.com_a,
            title=title,
            kind=StoryKind.RELATO,
            visibility=visibility,
            **extra,
        )
        add_consent(story)
        story.publish(by=self.autoridad_a)
        return story


class VisibilityQuerySetTests(TestCase, BaseFixture):
    def setUp(self):
        self.build()

    def titles(self, user):
        return set(Story.objects.visible_for(user).values_list("title", flat=True))

    def test_anonimo_solo_ve_lo_publico(self):
        self.assertEqual(self.titles(None), {"Pública"})

    def test_registrado_sin_comunidad(self):
        self.assertEqual(self.titles(self.registrado), {"Pública", "Registrada"})

    def test_solicitud_pendiente_no_da_acceso_a_la_comunidad(self):
        self.assertNotIn("De comunidad", self.titles(self.registrado))

    def test_miembro_ve_lo_de_su_comunidad(self):
        self.assertEqual(
            self.titles(self.miembro_a),
            {"Pública", "Registrada", "De comunidad", "Restringida"},
        )  # "Restringida" por ser la autoría

    def test_miembro_de_otra_comunidad_no_ve_lo_ajeno(self):
        self.assertEqual(self.titles(self.miembro_b), {"Pública", "Registrada"})

    def test_restringida_requiere_permiso_nominal(self):
        self.assertNotIn("Restringida", self.titles(self.miembro_b))
        StoryAccessGrant.objects.create(
            story=self.restringida, user=self.miembro_b, granted_by=self.autoridad_a
        )
        self.assertIn("Restringida", self.titles(self.miembro_b))

    def test_moderacion_ve_todo_lo_publicado(self):
        self.assertEqual(len(self.titles(self.moderador)), 4)

    def test_borrador_no_aparece_para_terceros(self):
        borrador = Story.objects.create(
            author=self.miembro_a, community=self.com_a, title="Borrador",
            visibility=Visibility.PUBLIC,
        )
        self.assertNotIn("Borrador", self.titles(self.miembro_b))
        self.assertNotIn("Borrador", self.titles(None))
        self.assertTrue(borrador.can_be_seen_by(self.miembro_a))


class ConsentRuleTests(TestCase):
    def setUp(self):
        self.com = Community.objects.create(name="Comunidad C")
        self.autor = make_user("autor@test.co")
        Membership.objects.create(
            community=self.com, user=self.autor, status=Membership.Status.ACTIVE
        )

    def test_no_se_publica_sin_autorizacion(self):
        story = Story.objects.create(
            author=self.autor, community=self.com, title="Sin permiso",
            visibility=Visibility.COMMUNITY,
        )
        with self.assertRaises(ValidationError):
            story.publish()
        story.refresh_from_db()
        self.assertEqual(story.status, StoryStatus.DRAFT)

    def test_con_autorizacion_si_se_publica(self):
        story = Story.objects.create(
            author=self.autor, community=self.com, title="Con permiso",
            visibility=Visibility.COMMUNITY,
        )
        add_consent(story)
        story.publish()
        story.refresh_from_db()
        self.assertEqual(story.status, StoryStatus.PUBLISHED)
        self.assertIsNotNone(story.published_at)

    def test_status_publicado_directo_falla_en_clean(self):
        story = Story(
            author=self.autor, community=self.com, title="Atajo",
            visibility=Visibility.COMMUNITY, status=StoryStatus.PUBLISHED,
        )
        with self.assertRaises(ValidationError):
            story.full_clean()


class SensitiveContentTests(TestCase):
    def setUp(self):
        self.com = Community.objects.create(name="Comunidad D")
        self.autor = make_user("autor_d@test.co")
        Membership.objects.create(
            community=self.com, user=self.autor, status=Membership.Status.ACTIVE
        )

    def test_sensible_no_puede_ser_de_uso_abierto(self):
        story = Story(
            author=self.autor, community=self.com, title="Saber reservado",
            visibility=Visibility.PUBLIC, is_sensitive=True,
        )
        with self.assertRaises(ValidationError) as ctx:
            story.full_clean()
        self.assertIn("visibility", ctx.exception.message_dict)

    def test_sensible_oculta_coordenadas(self):
        story = Story.objects.create(
            author=self.autor, community=self.com, title="Lugar reservado",
            visibility=Visibility.RESTRICTED, is_sensitive=True,
            place_name="Zona alta", latitude="10.5", longitude="-73.5",
        )
        location = story.public_location
        self.assertTrue(location["approximate"])
        self.assertNotIn("latitude", location)

    def test_comunidad_obligatoria_si_visibilidad_es_comunidad(self):
        story = Story(
            author=self.autor, title="Sin comunidad", visibility=Visibility.COMMUNITY
        )
        with self.assertRaises(ValidationError) as ctx:
            story.full_clean()
        self.assertIn("community", ctx.exception.message_dict)


class StoryApiTests(APITestCase, BaseFixture):
    def setUp(self):
        self.build()
        self.list_url = reverse("historia-list")

    def test_muro_anonimo(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Pública"])

    def test_muro_autenticado(self):
        self.client.force_authenticate(self.miembro_b)
        response = self.client.get(self.list_url)
        titles = {item["title"] for item in response.data["results"]}
        self.assertEqual(titles, {"Pública", "Registrada"})

    def test_detalle_sin_acceso_da_404(self):
        self.client.force_authenticate(self.miembro_b)
        url = reverse("historia-detail", args=[self.de_comunidad.pk])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_crear_historia_queda_en_borrador(self):
        self.client.force_authenticate(self.miembro_a)
        response = self.client.post(
            self.list_url,
            {
                "title": "Nueva memoria",
                "body": "Texto",
                "kind": StoryKind.MEMORIA,
                "visibility": Visibility.COMMUNITY,
                "community": self.com_a.pk,
                "tags": ["memoria"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], StoryStatus.DRAFT)

    def test_no_se_puede_publicar_en_comunidad_ajena(self):
        self.client.force_authenticate(self.miembro_b)
        response = self.client.post(
            self.list_url,
            {"title": "Intruso", "visibility": Visibility.COMMUNITY, "community": self.com_a.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("community", response.data)

    def test_publicar_exige_autorizacion(self):
        story = Story.objects.create(
            author=self.miembro_a, community=self.com_a, title="Pendiente",
            visibility=Visibility.COMMUNITY, status=StoryStatus.IN_REVIEW,
        )
        self.client.force_authenticate(self.autoridad_a)
        url = reverse("historia-publicar", args=[story.pk])
        self.assertEqual(self.client.post(url, {}, format="json").status_code, 400)

        add_consent(story, scope=Consent.Scope.COMMUNITY)
        response = self.client.post(url, {"note": "Revisado"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], StoryStatus.PUBLISHED)

    def test_la_autoria_no_registra_su_propia_autorizacion(self):
        """Quien escribe no certifica su propio permiso."""
        story = Story.objects.create(
            author=self.miembro_a, community=self.com_a, title="Mi relato",
            visibility=Visibility.COMMUNITY, status=StoryStatus.IN_REVIEW,
        )
        url = reverse("historia-autorizaciones", args=[story.pk])
        payload = {
            "granted_by_name": "Yo mismo",
            "scope": Consent.Scope.OPEN,
            "granted_on": str(date.today()),
        }
        self.client.force_authenticate(self.miembro_a)
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 403)
        self.assertFalse(story.consents.exists())

    def test_la_autoridad_si_registra_la_autorizacion(self):
        story = Story.objects.create(
            author=self.miembro_a, community=self.com_a, title="Para autorizar",
            visibility=Visibility.COMMUNITY, status=StoryStatus.IN_REVIEW,
        )
        url = reverse("historia-autorizaciones", args=[story.pk])
        self.client.force_authenticate(self.autoridad_a)
        response = self.client.post(
            url,
            {
                "granted_by_name": "Autoridad de la comunidad",
                "granted_by_role": "Cabildo",
                "scope": Consent.Scope.COMMUNITY,
                "granted_on": str(date.today()),
                "conditions": "No sale de la comunidad.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        consent = story.consents.get()
        self.assertEqual(consent.recorded_by, self.autoridad_a)

    def test_la_administracion_registra_en_cualquier_comunidad(self):
        story = Story.objects.create(
            author=self.miembro_b, community=self.com_b, title="De otra comunidad",
            visibility=Visibility.COMMUNITY, status=StoryStatus.IN_REVIEW,
        )
        self.client.force_authenticate(self.moderador)
        response = self.client.post(
            reverse("historia-autorizaciones", args=[story.pk]),
            {"granted_by_name": "Administración", "scope": Consent.Scope.OPEN,
             "granted_on": str(date.today())},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)

    def test_la_autoria_si_puede_leer_sus_autorizaciones(self):
        self.client.force_authenticate(self.miembro_a)
        url = reverse("historia-autorizaciones", args=[self.publica.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_enviar_a_revision_no_exige_autorizacion(self):
        """La autorización llega después, en la revisión."""
        story = Story.objects.create(
            author=self.miembro_a, community=self.com_a, title="Recién escrita",
            visibility=Visibility.COMMUNITY,
        )
        self.client.force_authenticate(self.miembro_a)
        response = self.client.post(
            reverse("historia-enviar-a-revision", args=[story.pk]), {}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], StoryStatus.IN_REVIEW)

    def test_miembro_raso_no_publica(self):
        story = Story.objects.create(
            author=self.miembro_a, community=self.com_a, title="Mía",
            visibility=Visibility.COMMUNITY, status=StoryStatus.IN_REVIEW,
        )
        add_consent(story)
        self.client.force_authenticate(self.miembro_a)
        url = reverse("historia-publicar", args=[story.pk])
        self.assertEqual(self.client.post(url, {}, format="json").status_code, 403)

    def test_aprecio_suma_y_resta(self):
        self.client.force_authenticate(self.miembro_b)
        url = reverse("historia-aprecio", args=[self.publica.pk])
        self.assertEqual(self.client.post(url, {}, format="json").data["like_count"], 1)
        self.assertEqual(self.client.post(url, {}, format="json").data["like_count"], 1)
        self.assertEqual(self.client.delete(url).data["like_count"], 0)

    def test_comentario_requiere_acceso(self):
        url = reverse("comentario-list")
        self.client.force_authenticate(self.miembro_b)
        response = self.client.post(
            url, {"story": self.de_comunidad.pk, "body": "Hola"}, format="json"
        )
        self.assertIn(response.status_code, {400, 403})

    def test_comentario_de_miembro(self):
        self.client.force_authenticate(self.miembro_a)
        response = self.client.post(
            reverse("comentario-list"),
            {"story": self.de_comunidad.pk, "body": "Gracias"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.de_comunidad.refresh_from_db()
        self.assertEqual(self.de_comunidad.comment_count, 1)

    def test_mapa_excluye_lo_sensible(self):
        Story.objects.filter(pk=self.publica.pk).update(
            latitude="10.5", longitude="-73.5"
        )
        sensible = Story.objects.create(
            author=self.miembro_a, community=self.com_a, title="Sitio reservado",
            visibility=Visibility.COMMUNITY, is_sensitive=True,
            latitude="10.9", longitude="-73.9",
        )
        add_consent(sensible)
        sensible.publish(by=self.autoridad_a)

        self.client.force_authenticate(self.miembro_a)
        response = self.client.get(reverse("historia-mapa"))
        titles = {point["title"] for point in response.data}
        self.assertIn("Pública", titles)
        self.assertNotIn("Sitio reservado", titles)


class AuthApiTests(APITestCase):
    def test_registro_exige_aceptar_criterios(self):
        url = reverse("registro")
        payload = {
            "email": "nueva@test.co",
            "display_name": "Nueva",
            "password": "clave-de-prueba-123",
            "accept_care_terms": False,
        }
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 400)
        payload["accept_care_terms"] = True
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNotNone(response.data["accepted_care_terms_at"])

    def test_login_devuelve_usuario(self):
        make_user("login@test.co")
        response = self.client.post(
            reverse("login"),
            {"email": "login@test.co", "password": "clave-de-prueba-123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertEqual(response.data["user"]["email"], "login@test.co")
