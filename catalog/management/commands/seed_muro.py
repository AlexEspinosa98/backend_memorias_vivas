"""
Datos de demostración del muro.

Crea comunidades, personas (un líder por comunidad y miembros) e historias
que cubren los cuatro niveles de acceso y el flujo de autorización completo.

El contenido se apoya en los temas documentados del archivo (tejido, café,
lengua, territorio) y **no es material cultural real**: son textos de prueba
redactados por el equipo para poder ver la plataforma funcionando. Cada
autorización lo dice de forma explícita en sus condiciones.

Idempotente.

    python manage.py seed_muro
    python manage.py seed_muro --reset    # borra lo sembrado y lo vuelve a crear
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
    MediaItem,
    Promotion,
    Reaction,
    Story,
    StoryAccessGrant,
    StoryKind,
    StoryStatus,
    Tag,
    Visibility,
    Visit,
)

User = get_user_model()

CLAVE = "contra123"
DOMINIO = "@memoriasvivas.co"

NOTA_DEMO = (
    "Contenido de demostración del prototipo, redactado por el equipo ALUNA IA. "
    "No es material cultural real ni sustituye la autorización de la comunidad."
)

# Coordenadas: Nabusímake es la real (OpenStreetMap la registra como
# «Nabusimake / San Sebastián de Rábago», 10.56139 N, 73.58556 W). Séynimin e
# Ikarwa son asentamientos pequeños que no están en ningún geocodificador
# público: sus coordenadas son aproximadas, ubicadas en la vertiente y la
# cuenca que cada una habita, y así se indican en el muro.
COMMUNITIES = [
    {
        "name": "Nabusímake",
        "territory": "Resguardo Arhuaco de la Sierra Nevada",
        "municipality": "Pueblo Bello",
        "department": "Cesar",
        "latitude": "10.561390",
        "longitude": "-73.585560",
        "description": (
            "Uno de los centros más reconocidos del pueblo Arhuaco, con importancia "
            "cultural e histórica. No representa la totalidad del territorio ni de "
            "las comunidades Arhuacas."
        ),
    },
    {
        "name": "Séynimin",
        "territory": "Vertiente norte de la Sierra Nevada",
        "municipality": "Santa Marta",
        "department": "Magdalena",
        "latitude": "11.050000",
        "longitude": "-73.850000",
        "description": (
            "Comunidad de la vertiente norte, vinculada a procesos de defensa "
            "territorial y producción audiovisual propia."
        ),
    },
    {
        "name": "Ikarwa",
        "territory": "Cuenca alta del río Fundación",
        "municipality": "Fundación",
        "department": "Magdalena",
        "latitude": "10.650000",
        "longitude": "-74.000000",
        "description": "Comunidad de la cuenca alta, con trabajo en educación propia y tejido.",
    },
]

# (correo sin dominio, nombre, rol de plataforma, comunidad, rol en la comunidad)
PEOPLE = [
    ("admin", "Administración del archivo", "admin", None, None),
    ("lider", "Líder de Nabusímake", "autoridad", "Nabusímake", "autoridad"),
    ("persona1", "Persona 1", "miembro", "Nabusímake", "miembro"),
    ("lider2", "Líder de Séynimin", "autoridad", "Séynimin", "autoridad"),
    ("persona2", "Persona 2", "miembro", "Ikarwa", "miembro"),
    ("tejedoras", "Colectivo de Tejedoras", "miembro", "Ikarwa", "miembro"),
    ("visitante", "Persona visitante", "visitante", None, None),
    # Solicitud pendiente, para ver el flujo de aprobación del líder.
    ("solicitante", "Persona que solicita ingreso", "visitante", "Nabusímake", "pendiente"),
]

TAGS = [
    "tejido", "lengua ika", "territorio", "memoria", "educación propia",
    "café", "agricultura", "mujeres", "jóvenes",
]

# Imágenes de las historias: son las figuras del documento base, servidas como
# archivos estáticos del front (`public/figuras/`) y no desde MEDIA_ROOT, que
# en Vercel es efímero. Cada una conserva el crédito tal como lo trae el
# documento, como exige la nota metodológica del archivo.
MEDIA = {
    "El tejido de la mochila se empieza por el centro": (
        "/figuras/practica-tejido.jpg",
        "Práctica del tejido Arhuaco",
        "Fotografía tomada de Mujeres indígenas, por EL TIEMPO (2022).",
    ),
    "El café que baja de la cuenca alta": (
        "/figuras/labores-agricolas.jpg",
        "Recolección de caña de azúcar por integrantes del pueblo Arhuaco",
        "Fotografía de Laura Rodríguez Navarro, publicada por la Oficina de las "
        "Naciones Unidas contra la Droga y el Delito (UNODC), en Noticias ONU (2021).",
    ),
    "Por qué decimos Iku y no solo Arhuaco": (
        "/figuras/hombres-arhuacos.jpg",
        "Hombres Arhuacos",
        "Fotografía de Raúl Arboleda, publicada por AFP en NAIZ (2024).",
    ),
    "Mochilas tejidas por el colectivo de Ikarwa": (
        "/figuras/mochila-tradicional.jpg",
        "Mochila tradicional del pueblo Arhuaco",
        "Fotografía tomada de Jóvenes artesanos Arhuacos impulsan iniciativa de "
        "desarrollo artesanal, por SIART (2012), Artesanías de Colombia.",
    ),
    "Recorrido de intercambio con estudiantes": (
        "/figuras/sierra-nevada.jpg",
        "Sierra Nevada de Santa Marta",
        "Imagen tomada de Parque Nacional Natural Sierra Nevada de Santa Marta, "
        "por Colombia País (s. f.).",
    ),
    "Acuerdos de la reunión sobre educación propia": (
        "/figuras/poblacion-reunida.jpg",
        "Población Arhuaca reunida",
        "Fotografía de Óscar Pérez, publicada en ¿Qué está pasando con el Pueblo "
        "Arhuaco en el Cesar?, por Redacción Colombia (2022), El Espectador.",
    ),
    "Lo que contaba mi abuelo de los caminos viejos": (
        "/figuras/sierra-nevada-paisaje.jpg",
        "Paisaje de la Sierra Nevada de Santa Marta",
        "Fotografía tomada de Parque Nacional Natural Sierra Nevada de Santa Marta, "
        "por Parques Nacionales Naturales de Colombia (s. f.).",
    ),
    "Fotografías del taller de lana": (
        "/figuras/taller-lana.jpg",
        "Artesanas Arhuacas participan en un taller sobre la calidad de la lana",
        "Fotografía publicada por AGROSAVIA (2025), en el marco de un taller sobre "
        "la calidad de la lana y el tejido tradicional en Nabusímake.",
    ),
    # La historia restringida y sensible no lleva imagen, a propósito.
}


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
            borradas, _ = Story.objects.filter(
                author__email__endswith=DOMINIO
            ).delete()
            self.stdout.write(f"Borradas {borradas} filas de demostración.")

        self.communities = self._seed_communities()
        self.users = self._seed_people()
        for name in TAGS:
            Tag.objects.get_or_create(name=name)

        stories = self._seed_stories()
        self._seed_media(stories)
        self._seed_interactions(stories)

        publicadas = Story.objects.filter(status=StoryStatus.PUBLISHED).count()
        abiertas = Story.objects.filter(
            status=StoryStatus.PUBLISHED, visibility=Visibility.PUBLIC
        ).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"\nListo: {len(self.communities)} comunidades, {len(self.users)} personas, "
                f"{len(stories)} historias ({publicadas} publicadas, {abiertas} de uso abierto).\n"
                f"Todas las cuentas de demostración usan la clave: {CLAVE}"
            )
        )

    # ------------------------------------------------------------------
    def _seed_communities(self):
        communities = {}
        for data in COMMUNITIES:
            community, _ = Community.objects.update_or_create(
                name=data["name"], defaults=data
            )
            communities[community.name] = community
            self.stdout.write(f"· comunidad {community.name}")
        return communities

    def _seed_people(self):
        users = {}
        for slug, name, role, community_name, community_role in PEOPLE:
            email = f"{slug}{DOMINIO}"
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "display_name": name,
                    "role": role,
                    "place": community_name or "",
                    "accepted_care_terms_at": timezone.now(),
                    "is_staff": role == "admin",
                    "is_superuser": role == "admin",
                },
            )
            # La clave se restablece siempre: es una cuenta de demostración.
            user.set_password(CLAVE)
            user.save()
            users[slug] = user

            if community_name:
                estado = (
                    Membership.Status.PENDING
                    if community_role == "pendiente"
                    else Membership.Status.ACTIVE
                )
                Membership.objects.update_or_create(
                    community=self.communities[community_name],
                    user=user,
                    defaults={
                        "role": (
                            Membership.Role.AUTHORITY
                            if community_role == "autoridad"
                            else Membership.Role.MEMBER
                        ),
                        "status": estado,
                        "note": (
                            "Solicitud de prueba, para ver cómo la aprueba el líder."
                            if estado == Membership.Status.PENDING
                            else ""
                        ),
                    },
                )
            self.stdout.write(
                f"  {'+' if created else '·'} {email:<34} {role:<10} {community_name or ''}"
            )
        return users

    # ------------------------------------------------------------------
    def _publicar(self, story, *, autoriza, calidad, alcance, dias_atras, condiciones=""):
        """Registra la autorización (siempre a nombre de la administración) y publica."""
        Consent.objects.create(
            story=story,
            granted_by_name=autoriza,
            granted_by_role=calidad,
            community=story.community,
            scope=alcance,
            granted_on=date.today() - timedelta(days=dias_atras),
            conditions=f"{condiciones} {NOTA_DEMO}".strip(),
            recorded_by=self.users["admin"],
        )
        story.published_at = timezone.now() - timedelta(days=dias_atras)
        story.publish(by=self.users["admin"])
        return story

    def _crear(self, *, autor, comunidad, titulo, **extra):
        story, created = Story.objects.get_or_create(
            title=titulo,
            defaults={
                "author": self.users[autor],
                "community": self.communities[comunidad] if comunidad else None,
                **extra,
            },
        )
        return story, created

    def _seed_stories(self):
        hechas = []

        # --- 1. Uso abierto: el tejido -----------------------------------
        story, nueva = self._crear(
            autor="persona1",
            comunidad="Nabusímake",
            titulo="El tejido de la mochila se empieza por el centro",
            kind=StoryKind.SABER,
            summary="Cómo se aprende a tejer en casa, contado por quienes tejen.",
            body=(
                "La mochila se empieza por el centro, igual que el pensamiento. "
                "Primero la vuelta, después la figura. Lo que uno piensa mientras "
                "teje queda en el tejido.\n\n"
                "El aprendizaje no tiene horario ni salón: se aprende mirando, "
                "preguntando y deshaciendo muchas veces la misma vuelta. Las mayores "
                "corrigen con la mano, no con la palabra.\n\n"
                "Este relato comparte la práctica, no los significados de cada figura. "
                "Esos los explican las tejedoras directamente, a quien corresponde."
            ),
            visibility=Visibility.PUBLIC,
            place_name="Nabusímake, Pueblo Bello (Cesar)",
            latitude="10.561390",
            longitude="-73.585560",
            language="es",
        )
        if nueva:
            story.tags.set(Tag.objects.filter(name__in=["tejido", "memoria", "mujeres"]))
            self._publicar(
                story, autoriza="Líder de Nabusímake",
                calidad="Autoridad de la comunidad", alcance=Consent.Scope.OPEN,
                dias_atras=24,
                condiciones="No se publican los significados de las figuras del tejido.",
            )
        hechas.append(story)

        # --- 2. Uso abierto: el café --------------------------------------
        story, nueva = self._crear(
            autor="persona2",
            comunidad="Ikarwa",
            titulo="El café que baja de la cuenca alta",
            kind=StoryKind.SABER,
            summary="La siembra cambia con la altura, y con ella cambia el trabajo del año.",
            body=(
                "En la cuenca alta se siembra según el piso térmico: maíz, fríjol, "
                "yuca, plátano, papa, hortalizas. El café llegó después y se quedó.\n\n"
                "La producción familiar y comunitaria sostiene el consumo diario y el "
                "intercambio entre zonas de clima distinto. Lo que sobra de una parte "
                "falta en la otra, y así se mueve.\n\n"
                "No todas las familias siembran igual ni lo mismo. Esto es lo que pasa "
                "aquí, no una descripción de todo el pueblo."
            ),
            visibility=Visibility.PUBLIC,
            place_name="Ikarwa, Fundación (Magdalena)",
            latitude="10.650000",
            longitude="-74.000000",
        )
        if nueva:
            story.tags.set(Tag.objects.filter(name__in=["café", "agricultura"]))
            self._publicar(
                story, autoriza="Líder de Nabusímake",
                calidad="Autoridad de la comunidad", alcance=Consent.Scope.OPEN,
                dias_atras=18,
            )
        hechas.append(story)

        # --- 3. Uso abierto: la lengua ------------------------------------
        story, nueva = self._crear(
            autor="lider",
            comunidad="Nabusímake",
            titulo="Por qué decimos Iku y no solo Arhuaco",
            kind=StoryKind.LENGUA,
            summary="Sobre el nombre propio del pueblo y las formas en que se escribe.",
            body=(
                "Iku es la palabra con la que el pueblo se nombra a sí mismo; suele "
                "traducirse como «gente». «Arhuaco» es la forma extendida en español.\n\n"
                "En documentos aparecen también Ika, Ikʉ e Ijku. No son errores: son "
                "maneras distintas de escribir una lengua que se transmite hablando.\n\n"
                "En este archivo usamos «pueblo Iku» o «pueblo Arhuaco». Antes de "
                "publicar palabras o audios en Ika se verifican con hablantes."
            ),
            visibility=Visibility.PUBLIC,
            place_name="Nabusímake",
            language="bilingue",
        )
        if nueva:
            story.tags.set(Tag.objects.filter(name__in=["lengua ika", "educación propia"]))
            self._publicar(
                story, autoriza="Líder de Nabusímake",
                calidad="Autoridad de la comunidad", alcance=Consent.Scope.OPEN,
                dias_atras=12,
            )
        hechas.append(story)

        # --- 4. Uso abierto: promoción ------------------------------------
        story, nueva = self._crear(
            autor="tejedoras",
            comunidad="Ikarwa",
            titulo="Mochilas tejidas por el colectivo de Ikarwa",
            kind=StoryKind.PROMOCION,
            summary="Tejido propio, por encargo. El acuerdo es directo con el colectivo.",
            body=(
                "El colectivo reúne a doce tejedoras de la cuenca alta. Cada mochila "
                "lleva el nombre de quien la teje y el tiempo que tomó.\n\n"
                "Los encargos se acuerdan directamente. La plataforma no cobra ni "
                "intermedia: solo sirve para que nos encuentren."
            ),
            visibility=Visibility.PUBLIC,
            place_name="Ikarwa, Fundación (Magdalena)",
            latitude="10.655000",
            longitude="-73.995000",
        )
        if nueva:
            story.tags.set(Tag.objects.filter(name__in=["tejido", "mujeres"]))
            Promotion.objects.create(
                story=story,
                category=Promotion.Category.ARTESANIA,
                contact="Colectivo de Tejedoras de Ikarwa",
                price_note="Según tamaño y tiempo de tejido; se acuerda por encargo.",
                active_until=date.today() + timedelta(days=120),
            )
            self._publicar(
                story, autoriza="Colectivo de Tejedoras de Ikarwa",
                calidad="Las propias artesanas", alcance=Consent.Scope.OPEN,
                dias_atras=15,
            )
        hechas.append(story)

        # --- 5. Personas registradas: visita -------------------------------
        story, nueva = self._crear(
            autor="lider2",
            comunidad="Séynimin",
            titulo="Recorrido de intercambio con estudiantes",
            kind=StoryKind.VISITA,
            summary="Dos días de conversación sobre territorio y educación propia.",
            body=(
                "La comunidad recibe un grupo pequeño para conversar sobre territorio "
                "y educación propia.\n\n"
                "Hay lugares a los que no se entra y momentos en los que no se toman "
                "fotografías. Eso no se negocia durante el recorrido: se acuerda antes."
            ),
            visibility=Visibility.REGISTERED,
            place_name="Séynimin, Santa Marta (Magdalena)",
            latitude="11.050000",
            longitude="-73.850000",
        )
        if nueva:
            story.tags.set(Tag.objects.filter(name__in=["territorio", "jóvenes"]))
            Visit.objects.create(
                story=story,
                starts_on=date.today() + timedelta(days=21),
                ends_on=date.today() + timedelta(days=22),
                meeting_point="Santa Marta, por confirmar con la comunidad",
                capacity=12,
                contact="Comité de Séynimin",
                conditions=(
                    "El recorrido se acuerda con la comunidad. No se ingresa a sitios "
                    "sagrados. Fotografía solo donde la comunidad lo autorice."
                ),
            )
            self._publicar(
                story, autoriza="Líder de Séynimin",
                calidad="Autoridad de la comunidad", alcance=Consent.Scope.OPEN,
                dias_atras=9,
                condiciones="No se fotografían espacios de pagamento.",
            )
        hechas.append(story)

        # --- 6. Solo la comunidad: aviso ------------------------------------
        story, nueva = self._crear(
            autor="lider",
            comunidad="Nabusímake",
            titulo="Acuerdos de la reunión sobre educación propia",
            kind=StoryKind.AVISO,
            summary="Resumen de los acuerdos para el próximo ciclo escolar.",
            body=(
                "La reunión acordó reforzar el uso de la lengua Ika en los primeros "
                "años y organizar encuentros mensuales con mayores.\n\n"
                "Queda pendiente definir quién acompaña los registros en audio y "
                "quién revisa las transcripciones antes de que se publiquen."
            ),
            visibility=Visibility.COMMUNITY,
            place_name="Nabusímake",
        )
        if nueva:
            story.tags.set(Tag.objects.filter(name__in=["educación propia", "lengua ika"]))
            self._publicar(
                story, autoriza="Líder de Nabusímake",
                calidad="Autoridad de la comunidad", alcance=Consent.Scope.COMMUNITY,
                dias_atras=4,
            )
        hechas.append(story)

        # --- 7. Solo la comunidad: memoria familiar --------------------------
        story, nueva = self._crear(
            autor="persona1",
            comunidad="Nabusímake",
            titulo="Lo que contaba mi abuelo de los caminos viejos",
            kind=StoryKind.MEMORIA,
            summary="Memoria familiar que la comunidad prefiere guardar entre nosotros.",
            body=(
                "Mi abuelo caminaba de una zona a otra antes de que hubiera carretera. "
                "Decía que el camino enseña más que la casa.\n\n"
                "Esta memoria se comparte dentro de la comunidad. No está lista para "
                "salir: faltan nombres por confirmar y hay que preguntarle a más gente."
            ),
            visibility=Visibility.COMMUNITY,
            place_name="Nabusímake",
        )
        if nueva:
            story.tags.set(Tag.objects.filter(name__in=["memoria", "territorio"]))
            self._publicar(
                story, autoriza="Familia de Persona 1",
                calidad="La familia del relato", alcance=Consent.Scope.COMMUNITY,
                dias_atras=2,
                condiciones="No sale de la comunidad hasta que se confirmen los nombres.",
            )
        hechas.append(story)

        # --- 8. Restringida y sensible ---------------------------------------
        story, nueva = self._crear(
            autor="lider2",
            comunidad="Séynimin",
            titulo="Registro de un recorrido de cuidado (acceso restringido)",
            kind=StoryKind.MEMORIA,
            summary="Material de consulta interna. No se divulga la ubicación.",
            body=(
                "Registro guardado para consulta interna de la comunidad.\n\n"
                "El contenido y la ubicación no se divulgan: la autorización cubre "
                "únicamente la consulta de las personas que la comunidad designe."
            ),
            visibility=Visibility.RESTRICTED,
            is_sensitive=True,
            place_name="Territorio de Séynimin",
            latitude="11.020000",
            longitude="-73.880000",
            allow_comments=False,
        )
        if nueva:
            self._publicar(
                story, autoriza="Autoridades de Séynimin",
                calidad="Autoridad de la comunidad", alcance=Consent.Scope.RESEARCH,
                dias_atras=1,
                condiciones="Consulta interna. No reproducir, no mapear, no transcribir sin revisión.",
            )
            StoryAccessGrant.objects.get_or_create(
                story=story,
                user=self.users["lider"],
                defaults={
                    "granted_by": self.users["lider2"],
                    "reason": "Intercambio entre autoridades de las dos comunidades.",
                },
            )
        hechas.append(story)

        # --- 9. En revisión: el flujo de autorización pendiente ---------------
        story, _ = self._crear(
            autor="persona1",
            comunidad="Nabusímake",
            titulo="Audio de un mayor hablando sobre el café",
            kind=StoryKind.TESTIMONIO,
            summary="Grabación de 8 minutos, a la espera de que la comunidad la revise.",
            body=(
                "Grabación hecha con permiso de la persona. La transcripción "
                "automática todavía no ha sido revisada, así que no debería "
                "publicarse tal como está.\n\n"
                "Falta que la autoridad registre la autorización y decida el alcance."
            ),
            visibility=Visibility.COMMUNITY,
            status=StoryStatus.IN_REVIEW,
            place_name="Nabusímake",
            language="bilingue",
        )
        hechas.append(story)

        # --- 10. Otra en revisión, de otra comunidad ---------------------------
        story, _ = self._crear(
            autor="persona2",
            comunidad="Ikarwa",
            titulo="Fotografías del taller de lana",
            kind=StoryKind.SABER,
            summary="Propuesta de publicación abierta, pendiente de autorización.",
            body=(
                "Fotografías del taller sobre la calidad de la lana y el tejido. "
                "Se propone publicarlas de forma abierta, con los créditos de quien "
                "las tomó.\n\n"
                "Falta la autorización de la comunidad y confirmar que las personas "
                "que aparecen están de acuerdo."
            ),
            visibility=Visibility.PUBLIC,
            status=StoryStatus.IN_REVIEW,
            place_name="Ikarwa, Fundación (Magdalena)",
        )
        hechas.append(story)

        for story in hechas:
            self.stdout.write(
                f"  · {story.get_status_display():<26} {story.get_visibility_display():<36} {story.title[:44]}"
            )
        return hechas

    # ------------------------------------------------------------------
    def _seed_media(self, stories):
        puestas = 0
        for story in stories:
            datos = MEDIA.get(story.title)
            if datos is None:
                continue
            url, caption, credit = datos
            _, creada = MediaItem.objects.update_or_create(
                story=story,
                external_url=url,
                defaults={
                    "kind": MediaItem.Kind.IMAGE,
                    "caption": caption,
                    "credit": credit,
                    "order": 0,
                },
            )
            puestas += 1
        self.stdout.write(f"  · {puestas} imágenes con su crédito")

    def _seed_interactions(self, stories):
        publicadas = [s for s in stories if s.status == StoryStatus.PUBLISHED]
        reacciones = {
            "El tejido de la mochila se empieza por el centro": [
                "persona2", "tejedoras", "visitante", "lider2",
            ],
            "El café que baja de la cuenca alta": ["persona1", "visitante"],
            "Por qué decimos Iku y no solo Arhuaco": ["persona1", "persona2", "tejedoras"],
            "Mochilas tejidas por el colectivo de Ikarwa": ["persona1", "visitante"],
        }
        for titulo, quienes in reacciones.items():
            story = next((s for s in publicadas if s.title == titulo), None)
            if story is None:
                continue
            for slug in quienes:
                Reaction.objects.get_or_create(
                    story=story, user=self.users[slug],
                    defaults={"kind": Reaction.Kind.LIKE},
                )

        comentarios = [
            (
                "El tejido de la mochila se empieza por el centro",
                "tejedoras",
                "Así nos enseñaron también en Ikarwa. Gracias por compartirlo.",
            ),
            (
                "El tejido de la mochila se empieza por el centro",
                "visitante",
                "Gracias por explicar hasta dónde se puede contar y hasta dónde no.",
            ),
            (
                "Por qué decimos Iku y no solo Arhuaco",
                "persona2",
                "Esto deberíamos ponerlo al principio del archivo.",
            ),
            (
                "Acuerdos de la reunión sobre educación propia",
                "persona1",
                "Yo puedo acompañar los registros en audio los sábados.",
            ),
        ]
        for titulo, slug, texto in comentarios:
            story = next((s for s in publicadas if s.title == titulo), None)
            if story is None or not story.allow_comments:
                continue
            Comment.objects.get_or_create(
                story=story, author=self.users[slug], body=texto
            )

        for story in publicadas:
            story.recount()
