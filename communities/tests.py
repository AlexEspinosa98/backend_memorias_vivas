"""
Pruebas de comunidades: listado, conteo de miembros y solicitudes de ingreso.

El listado tiene una trampa: `Community.member_count` es una propiedad del
modelo, así que una anotación con ese mismo nombre revienta con
`AttributeError: property has no setter`. `test_listado_anonimo` cubre eso.
"""
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from communities.models import Community, Membership

User = get_user_model()


def make_user(email, role="miembro"):
    return User.objects.create_user(
        email=email, password="clave-de-prueba-123",
        display_name=email.split("@")[0], role=role,
    )


class CommunityApiTests(APITestCase):
    def setUp(self):
        self.com = Community.objects.create(
            name="Nabusímake", municipality="Pueblo Bello", department="Cesar"
        )
        self.otra = Community.objects.create(name="Séynimin")

        self.autoridad = make_user("autoridad@test.co", role="autoridad")
        self.miembro = make_user("miembro@test.co")
        self.fuera = make_user("fuera@test.co", role="visitante")

        Membership.objects.create(
            community=self.com, user=self.autoridad,
            role=Membership.Role.AUTHORITY, status=Membership.Status.ACTIVE,
        )
        Membership.objects.create(
            community=self.com, user=self.miembro, status=Membership.Status.ACTIVE
        )
        # Pendiente: no debe contar como miembro.
        Membership.objects.create(
            community=self.com, user=self.fuera, status=Membership.Status.PENDING
        )

        self.list_url = reverse("comunidad-list")

    def test_listado_anonimo(self):
        """Regresión: el listado devolvía 500 por la anotación member_count."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 2)

    def test_conteo_solo_cuenta_miembros_activos(self):
        response = self.client.get(self.list_url)
        por_nombre = {c["name"]: c for c in response.data["results"]}
        self.assertEqual(por_nombre["Nabusímake"]["member_count"], 2)
        self.assertEqual(por_nombre["Séynimin"]["member_count"], 0)

    def test_detalle_trae_el_conteo(self):
        url = reverse("comunidad-detail", args=[self.com.slug])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["member_count"], 2)

    def test_my_membership_segun_quien_consulta(self):
        url = reverse("comunidad-detail", args=[self.com.slug])
        self.assertIsNone(self.client.get(url).data["my_membership"])

        self.client.force_authenticate(self.miembro)
        data = self.client.get(url).data["my_membership"]
        self.assertEqual(data, {"role": "miembro", "status": "activo"})

    def test_solicitar_ingreso(self):
        self.client.force_authenticate(self.fuera)
        url = reverse("comunidad-solicitar", args=[self.otra.slug])
        response = self.client.post(url, {"note": "Me presenta mi tía"}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "pendiente")

    def test_solicitar_dos_veces_no_duplica(self):
        self.client.force_authenticate(self.fuera)
        url = reverse("comunidad-solicitar", args=[self.otra.slug])
        self.client.post(url, {}, format="json")
        self.client.post(url, {}, format="json")
        self.assertEqual(
            Membership.objects.filter(community=self.otra, user=self.fuera).count(), 1
        )

    def test_comunidad_cerrada_rechaza_solicitudes(self):
        self.otra.is_open_to_requests = False
        self.otra.save()
        self.client.force_authenticate(self.fuera)
        url = reverse("comunidad-solicitar", args=[self.otra.slug])
        self.assertEqual(self.client.post(url, {}, format="json").status_code, 400)

    def test_solo_la_autoridad_decide(self):
        membership = Membership.objects.get(community=self.com, user=self.fuera)
        url = reverse(
            "comunidad-decidir", args=[self.com.slug, membership.id]
        )

        self.client.force_authenticate(self.miembro)
        self.assertEqual(
            self.client.post(url, {"status": "activo"}, format="json").status_code, 403
        )

        self.client.force_authenticate(self.autoridad)
        response = self.client.post(url, {"status": "activo"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        membership.refresh_from_db()
        self.assertEqual(membership.status, Membership.Status.ACTIVE)
        self.assertEqual(membership.decided_by, self.autoridad)

    def test_crear_comunidad_requiere_administracion(self):
        self.client.force_authenticate(self.miembro)
        self.assertEqual(
            self.client.post(self.list_url, {"name": "Nueva"}, format="json").status_code,
            403,
        )

        admin = make_user("admin@test.co", role="admin")
        self.client.force_authenticate(admin)
        response = self.client.post(self.list_url, {"name": "Nueva"}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["slug"], "nueva")
