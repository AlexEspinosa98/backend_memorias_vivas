"""
Pruebas de la capa de IA.

Lo que se verifica aquí es, sobre todo, que las cinco reglas se cumplan: qué
contenido puede leer un modelo, qué nunca sale del servidor, y que nada de lo
que produzca se publique solo.
"""
from datetime import date
from unittest.mock import patch

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
from ai.assistant import construir_contexto, tema_vedado
from catalog.models import ArchiveSection
from ai.models import AiAuditLog, AiSuggestion, AssistantQuery, CareTerm
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


class AssistantTests(APITestCase, Fixture):
    """
    El asistente responde solo con el archivo, y hay temas que no toca.

    Ninguna prueba llama al modelo: lo que se verifica es lo que pasa ANTES y
    DESPUÉS de esa llamada, que es donde están las reglas.
    """

    def setUp(self):
        self.build()
        self.url = reverse("asistente")
        # Una sección publicada: sin fuentes el asistente responde «no está»
        # antes de llegar al modelo, y no se probaría nada de lo que sigue.
        ArchiveSection.objects.create(
            number=6, title="Cultura y tradiciones",
            lead="Vestimenta, tejidos y mochilas.",
            body="La mochila es uno de los elementos más reconocidos.",
        )

    # --- temas vedados ---------------------------------------------------
    def test_pagamento_no_se_responde(self):
        response = self.client.post(
            self.url, {"pregunta": "¿Cómo se hace un pagamento?"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["estado"], "vedada")
        self.assertIn("autoridades de la comunidad", response.data["respuesta"])

    def test_sitios_sagrados_no_se_responden(self):
        for pregunta in [
            "dónde quedan los sitios sagrados",
            "qué es la Línea Negra",
            "explícame la Ley de Origen",
        ]:
            with self.subTest(pregunta=pregunta):
                response = self.client.post(
                    self.url, {"pregunta": pregunta}, format="json"
                )
                self.assertEqual(response.data["estado"], "vedada")

    def test_el_veto_ignora_tildes_y_mayusculas(self):
        response = self.client.post(
            self.url, {"pregunta": "QUE ES LA LINEA NEGRA"}, format="json"
        )
        self.assertEqual(response.data["estado"], "vedada")

    def test_los_terminos_de_la_comunidad_tambien_vetan(self):
        CareTerm.objects.create(
            term="ezwama", kind=CareTerm.Kind.KNOWLEDGE, community=self.com
        )
        self.assertEqual(tema_vedado("qué es un ezwama"), "ezwama")

    def test_un_tema_vedado_no_llega_al_modelo(self):
        """Se rechaza antes de construir contexto: el tema no sale del servidor."""
        with patch("ai.assistant.preguntar_a_gemini") as modelo:
            self.client.post(self.url, {"pregunta": "un pagamento"}, format="json")
        modelo.assert_not_called()

    def test_queda_registrado_qué_se_rechazó(self):
        self.client.post(self.url, {"pregunta": "un pagamento"}, format="json")
        consulta = AssistantQuery.objects.get()
        self.assertEqual(consulta.status, AssistantQuery.Status.REFUSED)
        self.assertEqual(consulta.blocked_by, "pagamento")

    # --- sin proveedor configurado ---------------------------------------
    def test_sin_clave_lo_dice_en_vez_de_inventar(self):
        response = self.client.post(
            self.url, {"pregunta": "¿Cómo se teje una mochila?"}, format="json"
        )
        self.assertEqual(response.data["estado"], "no_disponible")
        self.assertEqual(response.data["fuentes"], [])

    # --- el contexto respeta los permisos --------------------------------
    def test_el_contexto_solo_trae_lo_que_la_persona_ve(self):
        s = self.story("Relato de la comunidad", body="Sobre el tejido")
        add_consent(s)
        s.publish(by=self.autoridad)

        titulos_miembro = {f["titulo"] for f in construir_contexto(self.autor)}
        self.assertIn("Relato de la comunidad", titulos_miembro)

        titulos_anonimo = {f["titulo"] for f in construir_contexto(None)}
        self.assertNotIn("Relato de la comunidad", titulos_anonimo)

    def test_lo_sensible_nunca_entra_al_contexto(self):
        s = self.story(
            "Reservada", is_sensitive=True, visibility=Visibility.RESTRICTED,
            body="No debe salir",
        )
        add_consent(s, scope=Consent.Scope.RESEARCH)
        s.publish(by=self.autoridad)
        titulos = {f["titulo"] for f in construir_contexto(self.autoridad)}
        self.assertNotIn("Reservada", titulos)

    # --- la respuesta ------------------------------------------------------
    @patch("ai.assistant.gemini_disponible", return_value=(True, ""))
    @patch("ai.assistant.preguntar_a_gemini", return_value="NO_ESTA")
    def test_si_no_esta_en_el_archivo_lo_dice(self, _modelo, _disp):
        response = self.client.post(
            self.url, {"pregunta": "¿Cuántos habitantes hay?"}, format="json"
        )
        self.assertEqual(response.data["estado"], "sin_datos")
        self.assertIn("No encontré eso en el archivo", response.data["respuesta"])

    @patch("ai.assistant.gemini_disponible", return_value=(True, ""))
    @patch(
        "ai.assistant.preguntar_a_gemini",
        return_value="El tejido se aprende en casa [1]. Las mayores corrigen [1].",
    )
    def test_devuelve_solo_las_fuentes_citadas(self, _modelo, _disp):
        response = self.client.post(
            self.url, {"pregunta": "¿Cómo se aprende a tejer?"}, format="json"
        )
        self.assertEqual(response.data["estado"], "respondida")
        self.assertEqual(len(response.data["fuentes"]), 1)
        self.assertEqual(response.data["fuentes"][0]["numero"], 1)

    @patch("ai.assistant.gemini_disponible", return_value=(True, ""))
    @patch("ai.assistant.preguntar_a_gemini", return_value="Una respuesta [2].")
    def test_toda_consulta_queda_en_auditoria(self, _modelo, _disp):
        self.client.post(self.url, {"pregunta": "algo del archivo"}, format="json")
        consulta = AssistantQuery.objects.get()
        self.assertEqual(consulta.status, AssistantQuery.Status.ANSWERED)
        self.assertEqual(consulta.provider, "gemini")

    def test_pregunta_vacia_se_rechaza(self):
        response = self.client.post(self.url, {"pregunta": "  "}, format="json")
        self.assertEqual(response.status_code, 400)


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
