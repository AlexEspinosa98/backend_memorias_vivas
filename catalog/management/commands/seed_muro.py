"""
Datos de demostración del muro: comunidades, personas e historias de ejemplo.

Contenido ficticio de prueba, no material cultural real. Idempotente.

    python manage.py seed_muro
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from communities.models import Community, Membership
from stories.models import (
    Comment,
    Consent,
    Promotion,
    Reaction,
    Story,
    StoryKind,
    StoryStatus,
    Tag,
    Visibility,
    Visit,
)

User = get_user_model()

COMMUNITIES = [
    {
        "name": "Nabusímake",
        "territory": "Resguardo Arhuaco de la Sierra Nevada",
        "municipality": "Pueblo Bello",
        "department": "Cesar",
        "latitude": "10.577000",
        "longitude": "-73.587000",
        "description": "Centro reconocido del pueblo Arhuaco, con importancia cultural e histórica.",
    },
    {
        "name": "Séynimin",
        "territory": "Vertiente norte de la Sierra Nevada",
        "municipality": "Santa Marta",
        "department": "Magdalena",
        "description": "Comunidad de la vertiente norte vinculada a procesos de defensa territorial.",
    },
    {
        "name": "Ikarwa",
        "territory": "Cuenca alta del río Fundación",
        "municipality": "Fundación",
        "department": "Magdalena",
        "description": "Comunidad de la cuenca alta, con trabajo en educación propia.",
    },
]

PEOPLE = [
    ("mamo.zalabata@memoriasvivas.co", "Zalabata Torres", "autoridad", "Nabusímake"),
    ("ana.izquierdo@memoriasvivas.co", "Ana Izquierdo", "miembro", "Nabusímake"),
    ("juan.villafane@memoriasvivas.co", "Juan Villafañe", "moderador", "Séynimin"),
    ("tejedoras@memoriasvivas.co", "Colectivo de Tejedoras", "miembro", "Ikarwa"),
    ("visitante@memoriasvivas.co", "Persona visitante", None, None),
]

DEMO_PASSWORD = "memorias2026"


class Command(BaseCommand):
    help = "Siembra comunidades, personas e historias de demostración."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Borra las historias de demostración antes de sembrar.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            Story.objects.filter(author__email__endswith="@memoriasvivas.co").delete()
            self.stdout.write("Historias de demostración borradas.")

        communities = {}
        for data in COMMUNITIES:
            community, _ = Community.objects.update_or_create(
                name=data["name"], defaults=data
            )
            communities[community.name] = community

        users = {}
        for email, name, role, community_name in PEOPLE:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "display_name": name,
                    "role": "autoridad" if role == "autoridad" else (
                        "moderador" if role == "moderador" else "miembro" if role else "visitante"
                    ),
                    "place": community_name or "",
                    "accepted_care_terms_at": timezone.now(),
                },
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
            users[email] = user
            if community_name:
                Membership.objects.update_or_create(
                    community=communities[community_name],
                    user=user,
                    defaults={
                        "role": role if role in {"autoridad", "moderador"} else "miembro",
                        "status": Membership.Status.ACTIVE,
                    },
                )

        admin, created = User.objects.get_or_create(
            email="admin@memoriasvivas.co",
            defaults={
                "display_name": "Administración",
                "role": "admin",
                "is_staff": True,
                "is_superuser": True,
                "accepted_care_terms_at": timezone.now(),
            },
        )
        if created:
            admin.set_password(DEMO_PASSWORD)
            admin.save()

        for name in ["tejido", "lengua ika", "territorio", "memoria", "educación propia", "café"]:
            Tag.objects.get_or_create(name=name)

        stories = self._seed_stories(users, communities)
        self._seed_interactions(stories, users)

        self.stdout.write(
            self.style.SUCCESS(
                f"Listo: {len(communities)} comunidades, {User.objects.count()} personas, "
                f"{len(stories)} historias. Clave de demostración: {DEMO_PASSWORD}"
            )
        )

    # ------------------------------------------------------------------
    def _story(self, *, author, community, title, **kwargs):
        story, created = Story.objects.get_or_create(
            title=title,
            defaults={"author": author, "community": community, **kwargs},
        )
        return story, created

    def _seed_stories(self, users, communities):
        made = []

        # 1. Uso abierto, con autorización de uso abierto.
        story, created = self._story(
            author=users["ana.izquierdo@memoriasvivas.co"],
            community=communities["Nabusímake"],
            title="El tejido como forma de pensamiento",
            kind=StoryKind.SABER,
            summary="Las tejedoras cuentan cómo se aprende a tejer la mochila en casa.",
            body=(
                "Mi abuela decía que la mochila se empieza por el centro, igual que el "
                "pensamiento. Primero la vuelta, después la figura. Lo que uno piensa "
                "mientras teje queda en el tejido.\n\n"
                "Este relato se comparte con autorización de la familia para que las nuevas "
                "generaciones conozcan la práctica, sin explicar los significados de cada figura: "
                "eso lo enseñan las tejedoras directamente."
            ),
            visibility=Visibility.PUBLIC,
            place_name="Nabusímake, Pueblo Bello (Cesar)",
            latitude="10.577000",
            longitude="-73.587000",
            language="es",
        )
        if created:
            Consent.objects.create(
                story=story,
                granted_by_name="Familia Izquierdo",
                granted_by_role="La persona del relato y su familia",
                community=communities["Nabusímake"],
                scope=Consent.Scope.OPEN,
                granted_on=date.today() - timedelta(days=20),
                conditions="No se publican los significados de las figuras del tejido.",
            )
            story.tags.set(Tag.objects.filter(name__in=["tejido", "memoria"]))
            story.publish(by=users["mamo.zalabata@memoriasvivas.co"])
        made.append(story)

        # 2. Solo comunidad.
        story, created = self._story(
            author=users["mamo.zalabata@memoriasvivas.co"],
            community=communities["Nabusímake"],
            title="Acuerdos de la reunión sobre educación propia",
            kind=StoryKind.AVISO,
            summary="Resumen de los acuerdos para el próximo ciclo escolar.",
            body=(
                "La reunión acordó reforzar el uso de la lengua Ika en los primeros años y "
                "organizar encuentros mensuales con mayores. Queda pendiente definir quién "
                "acompaña los registros en audio."
            ),
            visibility=Visibility.COMMUNITY,
            place_name="Nabusímake",
            language="es",
        )
        if created:
            Consent.objects.create(
                story=story,
                granted_by_name="Autoridades de Nabusímake",
                granted_by_role="Autoridad de la comunidad",
                community=communities["Nabusímake"],
                scope=Consent.Scope.COMMUNITY,
                granted_on=date.today() - timedelta(days=5),
            )
            story.tags.set(Tag.objects.filter(name__in=["educación propia", "lengua ika"]))
            story.publish(by=users["mamo.zalabata@memoriasvivas.co"])
        made.append(story)

        # 3. Sensible + restringido: no se mapea, requiere permiso nominal.
        story, created = self._story(
            author=users["juan.villafane@memoriasvivas.co"],
            community=communities["Séynimin"],
            title="Registro de un recorrido de cuidado (acceso restringido)",
            kind=StoryKind.MEMORIA,
            summary="Material de consulta interna. No se divulga la ubicación.",
            body=(
                "Registro guardado para consulta interna de la comunidad. El contenido y la "
                "ubicación no se divulgan: la autorización cubre únicamente la consulta de "
                "las personas designadas por la comunidad."
            ),
            visibility=Visibility.RESTRICTED,
            is_sensitive=True,
            place_name="Territorio de Séynimin",
            latitude="11.100000",
            longitude="-73.900000",
            allow_comments=False,
        )
        if created:
            Consent.objects.create(
                story=story,
                granted_by_name="Autoridades de Séynimin",
                granted_by_role="Autoridad de la comunidad",
                community=communities["Séynimin"],
                scope=Consent.Scope.RESEARCH,
                granted_on=date.today() - timedelta(days=2),
                conditions="Consulta interna. No reproducir, no mapear, no transcribir sin revisión.",
            )
            story.publish(by=users["juan.villafane@memoriasvivas.co"])
        made.append(story)

        # 4. Visita / recorrido, registrado.
        story, created = self._story(
            author=users["juan.villafane@memoriasvivas.co"],
            community=communities["Séynimin"],
            title="Recorrido de intercambio con estudiantes",
            kind=StoryKind.VISITA,
            summary="Dos días de intercambio con acuerdos de respeto definidos por la comunidad.",
            body=(
                "La comunidad recibe un grupo pequeño para conversar sobre territorio y "
                "educación propia. Hay lugares a los que no se entra y momentos en los que "
                "no se toman fotografías."
            ),
            visibility=Visibility.REGISTERED,
            place_name="Séynimin, Santa Marta (Magdalena)",
            latitude="11.150000",
            longitude="-73.950000",
        )
        if created:
            Consent.objects.create(
                story=story,
                granted_by_name="Autoridades de Séynimin",
                granted_by_role="Autoridad de la comunidad",
                community=communities["Séynimin"],
                scope=Consent.Scope.OPEN,
                granted_on=date.today() - timedelta(days=10),
                conditions="No se fotografían espacios de pagamento.",
            )
            Visit.objects.create(
                story=story,
                starts_on=date.today() + timedelta(days=21),
                ends_on=date.today() + timedelta(days=22),
                meeting_point="Santa Marta, por confirmar con la comunidad",
                capacity=12,
                contact="Comité de Séynimin",
                conditions=(
                    "Se acuerda con la comunidad el recorrido. No se ingresa a sitios sagrados. "
                    "Fotografía solo donde la comunidad lo autorice."
                ),
            )
            story.tags.set(Tag.objects.filter(name__in=["territorio", "educación propia"]))
            story.publish(by=users["juan.villafane@memoriasvivas.co"])
        made.append(story)

        # 5. Promoción, uso abierto.
        story, created = self._story(
            author=users["tejedoras@memoriasvivas.co"],
            community=communities["Ikarwa"],
            title="Mochilas tejidas por el colectivo de Ikarwa",
            kind=StoryKind.PROMOCION,
            summary="Tejido propio, por encargo. El contacto es directo con el colectivo.",
            body=(
                "El colectivo reúne a doce tejedoras de la cuenca alta. Los encargos se "
                "acuerdan directamente; cada mochila lleva el nombre de quien la teje."
            ),
            visibility=Visibility.PUBLIC,
            place_name="Ikarwa, Fundación (Magdalena)",
            latitude="10.700000",
            longitude="-74.100000",
        )
        if created:
            Consent.objects.create(
                story=story,
                granted_by_name="Colectivo de Tejedoras de Ikarwa",
                granted_by_role="Las propias artesanas",
                community=communities["Ikarwa"],
                scope=Consent.Scope.OPEN,
                granted_on=date.today() - timedelta(days=15),
            )
            Promotion.objects.create(
                story=story,
                category=Promotion.Category.ARTESANIA,
                contact="Colectivo de Tejedoras de Ikarwa",
                price_note="Según tamaño y tiempo de tejido; se acuerda por encargo.",
                active_until=date.today() + timedelta(days=120),
            )
            story.tags.set(Tag.objects.filter(name__in=["tejido"]))
            story.publish(by=users["mamo.zalabata@memoriasvivas.co"])
        made.append(story)

        # 6. En revisión: muestra el flujo de autorización pendiente.
        self._story(
            author=users["ana.izquierdo@memoriasvivas.co"],
            community=communities["Nabusímake"],
            title="Audio de un mayor hablando sobre el café (pendiente de autorización)",
            kind=StoryKind.TESTIMONIO,
            summary="Grabación en espera de que la comunidad revise la transcripción.",
            body="Grabación de 8 minutos. La transcripción automática debe ser revisada antes de publicar.",
            visibility=Visibility.COMMUNITY,
            status=StoryStatus.IN_REVIEW,
            place_name="Nabusímake",
            language="bilingue",
        )
        return made

    def _seed_interactions(self, stories, users):
        published = [s for s in stories if s.status == StoryStatus.PUBLISHED]
        if not published:
            return
        first = published[0]
        for email in ["juan.villafane@memoriasvivas.co", "tejedoras@memoriasvivas.co", "visitante@memoriasvivas.co"]:
            Reaction.objects.get_or_create(
                story=first, user=users[email], defaults={"kind": Reaction.Kind.LIKE}
            )
        Comment.objects.get_or_create(
            story=first,
            author=users["tejedoras@memoriasvivas.co"],
            body="Así nos enseñaron también en Ikarwa. Gracias por compartirlo.",
        )
        for story in published:
            story.recount()
