"""
Pruebas de la capa de IA.

Lo que se verifica aquí es, sobre todo, que las cinco reglas se cumplan: qué
contenido puede leer un modelo, qué nunca sale del servidor, y que nada de lo
que produzca se publique solo.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from ai.guards import (
    CareRuleViolation,
    community_allows,
    indexable_stories,
    may_process,
    visible_index_for,
)
from ai.models import AiAuditLog, AiSuggestion, CareTerm
from ai.providers import buscar_terminos
from ai.review import FEATURE, revisar, ultima_revision
from communities.models import Community, Membership
from stories.models import Consent, Story, StoryStatus, Visibility

User = get_user_model()


def make_user(email, role="miembro"):
    return User.objects.create_user(
        email=email, password="clave-de-prueba-123",
        display_name=email.split("@")[0], role=role,
    )


def add_consent(story, scope=Consent.Scope.OPEN):
    return Consent.objects.create(
        story=story, granted_by_name="Autoridad", community=story.community,
        scope=scope, granted_on=date.today(),
    )


class Fixture:
    def build(self, *, ia=True, externo=False):
        ajustes = {}
        if ia:
            ajustes[FEATURE] = True
        if externo:
            ajustes[f"{FEATURE}_externo"] = True

        self.com = Community.objects.create(name="Comunidad IA", ai_settings=ajustes)
        self.otra = Community.objects.create(name="Comunidad sin IA")

        self.autoridad = make_user("autoridad_ia@test.co", role="autoridad")
        self.autor = make_user("autor_ia@test.co")
        Membership.objects.create(
            community=self.com, user=self.autoridad,
            role=Membership.Role.AUTHORITY, status=Membership.Status.ACTIVE,
        )
        Membership.objects.create(
            community=self.com, user=self.autor, status=Membership.Status.ACTIVE
        )

        CareTerm.objects.create(
            term="pagamento", kind=CareTerm.Kind.PRACTICE,
            note="Verifique con la autoridad antes de publicar.",
        )
        CareTerm.objects.create(
            term="sitio sagrado", kind=CareTerm.Kind.PLACE, community=self.com
        )

    def story(self, title, **extra):
        extra.setdefault("visibility", Visibility.COMMUNITY)
        return Story.objects.create(
            author=self.autor, community=self.com, title=title, **extra
        )


class GuardTests(TestCase, Fixture):
    def setUp(self):
        self.build()

    def test_sin_autorizacion_no_entra_al_indice(self):
        self.story("Sin permiso")
        self.assertEqual(indexable_stories().count(), 0)

    def test_con_autorizacion_si_entra(self):
        add_consent(self.story("Con permiso"))
        self.assertEqual(indexable_stories().count(), 1)

    def test_lo_sensible_queda_fuera_del_indice(self):
        s = self.story("Reservada", is_sensitive=True, visibility=Visibility.RESTRICTED)
        add_consent(s)
        self.assertEqual(indexable_stories().count(), 0)

    def test_alcance_de_consulta_interna_no_alimenta_el_indice(self):
        add_consent(self.story("Interna"), scope=Consent.Scope.RESEARCH)
        self.assertEqual(indexable_stories().count(), 0)

    def test_un_borrador_no_entra_al_indice_de_nadie(self):
        """Autorizado pero sin publicar: no se indexa."""
        add_consent(self.story("Borrador"))
        self.assertEqual(indexable_stories().count(), 1)
        self.assertEqual(visible_index_for(self.autor).count(), 0)

    def test_el_indice_respeta_lo_que_cada_persona_ve(self):
        s = self.story("De la comunidad")
        add_consent(s)
        s.publish(by=self.autoridad)
        self.assertEqual(visible_index_for(self.autor).count(), 1)
        self.assertEqual(visible_index_for(make_user("fuera@test.co")).count(), 0)
        self.assertEqual(visible_index_for(None).count(), 0)

    def test_por_defecto_la_comunidad_no_activa_nada(self):
        self.assertFalse(community_allows(self.otra, FEATURE))
        self.assertTrue(community_allows(self.com, FEATURE))

    def test_sin_comunidad_no_corre(self):
        self.assertFalse(community_allows(None, FEATURE))

    def test_may_process_bloquea_si_la_comunidad_no_activo(self):
        s = Story.objects.create(
            author=self.autor, community=self.otra, title="Ajena",
            visibility=Visibility.COMMUNITY,
        )
        with self.assertRaises(CareRuleViolation):
            may_process(s, FEATURE)


class ExternalProviderTests(TestCase, Fixture):
    """Regla: lo sensible y lo restringido nunca salen del servidor."""

    def setUp(self):
        self.build(externo=True)

    def test_lo_sensible_nunca_sale(self):
        s = self.story("Reservada", is_sensitive=True, visibility=Visibility.RESTRICTED)
        may_process(s, FEATURE)  # local sí
        with self.assertRaises(CareRuleViolation) as ctx:
            may_process(s, FEATURE, external=True)
        self.assertIn("sensible", str(ctx.exception))

    def test_lo_restringido_tampoco_sale(self):
        s = self.story("Restringida", visibility=Visibility.RESTRICTED)
        with self.assertRaises(CareRuleViolation):
            may_process(s, FEATURE, external=True)

    def test_sin_autorizacion_explicita_no_sale(self):
        self.com.ai_settings = {FEATURE: True}
        self.com.save()
        s = self.story("Normal")
        may_process(s, FEATURE)
        with self.assertRaises(CareRuleViolation) as ctx:
            may_process(s, FEATURE, external=True)
        self.assertIn("proveedor externo", str(ctx.exception))


class TermMatchingTests(TestCase):
    def setUp(self):
        self.terms = [
            CareTerm(term="pagamento", kind=CareTerm.Kind.PRACTICE),
            CareTerm(term="Línea Negra", kind=CareTerm.Kind.PLACE),
        ]

    def test_encuentra_sin_importar_tildes_ni_mayusculas(self):
        hallazgos = buscar_terminos("Subimos a la LINEA NEGRA", self.terms)
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0]["tipo"], CareTerm.Kind.PLACE)

    def test_no_dispara_dentro_de_otra_palabra(self):
        self.assertEqual(buscar_terminos("El pagamentos no", self.terms), [])
        self.assertEqual(buscar_terminos("despagamento", self.terms), [])

    def test_texto_limpio_no_deja_hallazgos(self):
        self.assertEqual(buscar_terminos("Hoy tejimos una mochila", self.terms), [])


class ReviewTests(TestCase, Fixture):
    def setUp(self):
        self.build()

    def test_revisa_y_deja_sugerencia_pendiente(self):
        s = self.story("Relato", body="Hicimos un pagamento en la mañana.")
        sugerencia = revisar(s, user=self.autor)
        self.assertIsNotNone(sugerencia)
        self.assertEqual(sugerencia.status, AiSuggestion.Status.PENDING)
        self.assertEqual(len(sugerencia.findings), 1)
        self.assertIn("práctica ceremonial", sugerencia.payload["resumen"])

    def test_no_corre_si_la_comunidad_no_activo(self):
        s = Story.objects.create(
            author=self.autor, community=self.otra, title="Ajena",
            body="Un pagamento", visibility=Visibility.COMMUNITY,
        )
        self.assertIsNone(revisar(s))
        self.assertEqual(AiSuggestion.objects.count(), 0)

    def test_texto_limpio_tambien_deja_constancia(self):
        s = self.story("Tejido", body="Aprendimos a tejer la mochila.")
        sugerencia = revisar(s)
        self.assertEqual(sugerencia.findings, [])
        self.assertIn("No se encontró nada", sugerencia.payload["resumen"])

    def test_queda_registro_en_auditoria(self):
        s = self.story("Relato", body="Un pagamento")
        revisar(s, user=self.autor)
        log = AiAuditLog.objects.get()
        self.assertEqual(log.provider, "reglas")
        self.assertEqual(log.requested_by, self.autor)

    def test_revisar_dos_veces_no_duplica(self):
        s = self.story("Relato", body="Un pagamento")
        revisar(s)
        revisar(s)
        self.assertEqual(AiSuggestion.objects.filter(story=s).count(), 1)
        self.assertEqual(AiAuditLog.objects.filter(story=s).count(), 2)

    def test_la_ia_no_toca_el_contenido(self):
        s = self.story("Relato", body="Un pagamento")
        antes = (s.body, s.status, s.review_note)
        revisar(s)
        s.refresh_from_db()
        self.assertEqual((s.body, s.status, s.review_note), antes)


class ReviewApiTests(APITestCase, Fixture):
    def setUp(self):
        self.build()

    def test_enviar_a_revision_dispara_el_revisor(self):
        s = self.story("Relato", body="Hicimos un pagamento.")
        self.client.force_authenticate(self.autor)
        response = self.client.post(
            reverse("historia-enviar-a-revision", args=[s.pk]), {}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], StoryStatus.IN_REVIEW)
        self.assertIsNotNone(ultima_revision(s))

    def test_la_nota_es_solo_para_quien_decide(self):
        s = self.story("Relato", body="Un pagamento")
        revisar(s)
        url = reverse("historia-revision-ia", args=[s.pk])

        self.client.force_authenticate(self.autor)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_authenticate(self.autoridad)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["hallazgos"]), 1)

    def test_la_autoria_no_ve_la_nota_en_el_detalle(self):
        s = self.story("Relato", body="Un pagamento")
        revisar(s)
        self.client.force_authenticate(self.autor)
        detalle = self.client.get(reverse("historia-detail", args=[s.pk]))
        self.assertIsNone(detalle.data["care_review"])

    def test_la_autoridad_si_la_ve_en_el_detalle(self):
        s = self.story("Relato", body="Un pagamento")
        revisar(s)
        self.client.force_authenticate(self.autoridad)
        detalle = self.client.get(reverse("historia-detail", args=[s.pk]))
        self.assertIsNotNone(detalle.data["care_review"])
        self.assertEqual(len(detalle.data["care_review"]["hallazgos"]), 1)
