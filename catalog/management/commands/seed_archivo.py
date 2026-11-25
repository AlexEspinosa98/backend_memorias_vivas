"""
Siembra las 13 secciones del archivo y las fuentes del documento base.

Idempotente: se puede correr varias veces (upsert por `number` / `citation`).

    python manage.py seed_archivo
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import ArchiveSection, Figure, Source

SECTIONS = [
    {
        "number": 1,
        "title": "Inicio",
        "lead": "Memorias Vivas: un puente entre generaciones.",
        "body": (
            "Archivo digital dedicado a reunir, organizar y facilitar la consulta de "
            "contenidos culturales del pueblo Arhuaco, también conocido como Iku. La "
            "propuesta busca acercar a las nuevas generaciones a las memorias, los relatos "
            "y los conocimientos que la comunidad decida compartir.\n\n"
            "El archivo se plantea como una herramienta de apoyo. La tecnología no reemplaza "
            "la voz de los mayores ni la autoridad de la comunidad sobre sus conocimientos."
        ),
        "care_note": (
            "La memoria de nuestros mayores, el conocimiento de nuestras generaciones."
        ),
    },
    {
        "number": 2,
        "title": "¿Quiénes son los Arhuacos?",
        "lead": "El pueblo Arhuaco se autoidentifica como Iku, palabra que suele traducirse como «gente».",
        "body": (
            "Es uno de los cuatro pueblos indígenas de la Sierra Nevada de Santa Marta, junto "
            "con los pueblos Kogui, Wiwa y Kankuamo. Su identidad está relacionada con la lengua, "
            "el territorio, la espiritualidad, la organización comunitaria y los conocimientos "
            "transmitidos entre generaciones.\n\n"
            "En documentos institucionales y académicos también aparecen las formas Ika, Ikʉ e Ijku. "
            "La denominación «Arhuaco» es de uso extendido en español, mientras que Iku corresponde "
            "a una forma de autodenominación.\n\n"
            "Las fuentes históricas relacionan a los pueblos de la Sierra Nevada con sociedades "
            "indígenas anteriores a la conquista española, entre ellas la cultura conocida como Tairona."
        ),
        "care_note": (
            "Por respeto a esa identidad, en este archivo se utilizan las expresiones "
            "«pueblo Iku» o «pueblo Arhuaco»."
        ),
    },
    {
        "number": 3,
        "title": "Ubicación geográfica",
        "lead": "Sierra Nevada de Santa Marta: Magdalena, Cesar y La Guajira.",
        "body": (
            "El pueblo Arhuaco habita principalmente la Sierra Nevada de Santa Marta. Hay "
            "asentamientos en cuencas altas de ríos como Aracataca, Fundación y Ariguaní, así "
            "como en sectores de las vertientes norte y suroriental.\n\n"
            "Para estos pueblos la Sierra no representa únicamente un espacio físico: está "
            "vinculada con su historia, su espiritualidad y sus responsabilidades de cuidado.\n\n"
            "Nabusímake es uno de los centros más reconocidos del pueblo Arhuaco, pero no "
            "representa la totalidad del territorio ni de las comunidades.\n\n"
            "La Línea Negra es el sistema de espacios sagrados que articula el territorio ancestral "
            "de los cuatro pueblos. El Decreto 0514 de 2026 precisa su reconocimiento como ámbito "
            "tradicional de especial protección."
        ),
        "care_note": (
            "El archivo no publica la ubicación ni el significado de sitios sagrados. "
            "Los contenidos marcados como sensibles no se muestran en el mapa."
        ),
    },
    {
        "number": 4,
        "title": "Organización social y política",
        "lead": "Autoridades tradicionales, espacios comunitarios y representación política.",
        "body": (
            "Los Mamos son autoridades espirituales y sabedores: orientan asuntos relacionados "
            "con la Ley de Origen, la vida espiritual y el equilibrio con el territorio. Su "
            "autoridad debe comprenderse dentro de la tradición Iku y no equipararse automáticamente "
            "con cargos religiosos o políticos de otras sociedades.\n\n"
            "En la estructura organizativa también se mencionan figuras como el Cabildo Gobernador, "
            "los cabildos menores y los comisarios. Las funciones y relaciones entre autoridades "
            "pueden variar según los procesos organizativos y las comunidades."
        ),
        "care_note": (
            "No se presenta una única estructura como si fuera idéntica en todos los asentamientos. "
            "Cada comunidad del archivo define sus propias autoridades."
        ),
    },
    {
        "number": 5,
        "title": "Lengua y comunicación",
        "lead": "La lengua Ika o Iku pertenece a la familia lingüística chibchense.",
        "body": (
            "Es un componente fundamental de la identidad cultural y una forma de expresar "
            "conocimientos, experiencias y maneras de comprender el territorio y la vida comunitaria.\n\n"
            "La transmisión de la lengua se relaciona con su uso en la familia, la comunidad y los "
            "espacios educativos. La tradición oral permite compartir relatos, enseñanzas y memorias "
            "mediante la palabra y la escucha."
        ),
        "care_note": (
            "Antes de incorporar palabras, traducciones o audios en Ika se verifican con hablantes "
            "o materiales producidos y autorizados por la propia comunidad."
        ),
    },
    {
        "number": 6,
        "title": "Cultura y tradiciones",
        "lead": "Vestimenta, tejidos y mochilas.",
        "body": (
            "La vestimenta tradicional Arhuaca suele reconocerse por el uso de prendas blancas: "
            "túnicas o mantas y gorros tejidos. Las formas de vestir pueden presentar variaciones "
            "entre personas, comunidades y generaciones.\n\n"
            "La mochila es uno de los elementos culturales más reconocidos. El tejido reúne "
            "conocimientos prácticos y culturales que se transmiten entre generaciones; las mujeres "
            "tienen un papel central en la elaboración de artesanías y en la transmisión de "
            "pensamientos e historia mediante el tejido."
        ),
        "care_note": (
            "Alimentación, música y celebraciones no se desarrollan aquí: las fuentes revisadas no "
            "permiten describirlas de manera suficiente. Se incorporarán con fuentes específicas y "
            "autorización comunitaria. Los significados de diseños y símbolos se explican con la "
            "orientación de las tejedoras."
        ),
    },
    {
        "number": 7,
        "title": "Cosmovisión y espiritualidad",
        "lead": "La Sierra Nevada ocupa un lugar central; el territorio se comprende desde relaciones espirituales.",
        "body": (
            "La naturaleza no se presenta únicamente como un conjunto de recursos físicos: las "
            "montañas, el agua y otros elementos del entorno están vinculados con responsabilidades "
            "de cuidado y equilibrio.\n\n"
            "La Ley de Origen constituye un marco ancestral de principios y orientaciones para la "
            "relación con el territorio, la comunidad y los seres que lo habitan. Su comprensión "
            "pertenece a la tradición y a las autoridades propias.\n\n"
            "El Decreto 0514 de 2026 reconoce la Línea Negra como un sistema de espacios sagrados "
            "de especial protección y valor espiritual, cultural y ambiental."
        ),
        "care_note": (
            "No se detallan prácticas específicas de pagamento ni se divulga la ubicación o el "
            "significado de los sitios sagrados. Por respeto, esos contenidos no se desarrollan."
        ),
    },
    {
        "number": 8,
        "title": "Educación y saberes ancestrales",
        "lead": "La familia y la comunidad como espacios de transmisión.",
        "body": (
            "Las enseñanzas se comparten mediante la conversación, la observación, la participación "
            "en actividades y la orientación de personas mayores.\n\n"
            "La educación propia busca fortalecer la identidad y los conocimientos del pueblo. La "
            "oralidad es un recurso comunicativo y pedagógico para fortalecer las tradiciones "
            "culturales e integrar los saberes propios a los procesos educativos.\n\n"
            "El archivo puede organizar relatos, testimonios, audios, fotografías y otros registros "
            "autorizados. La inteligencia artificial podría apoyar su transcripción, clasificación y "
            "búsqueda, sin reemplazar la interpretación de quienes comparten los conocimientos."
        ),
        "care_note": "",
    },
    {
        "number": 9,
        "title": "Economía y actividades productivas",
        "lead": "Agricultura, artesanías y tejidos.",
        "body": (
            "Los productos cultivados varían según la altura y las condiciones climáticas: maíz, "
            "fríjol, yuca, plátano, papa, hortalizas y café, entre otros.\n\n"
            "La producción agrícola familiar y comunitaria contribuye al consumo cotidiano, al "
            "intercambio de productos entre zonas con diferentes climas y al sostenimiento de "
            "actividades colectivas.\n\n"
            "Las artesanías y los tejidos también hacen parte de las actividades culturales y económicas."
        ),
        "care_note": (
            "Las prácticas productivas no son iguales para todas las familias ni comunidades: "
            "estos datos son ejemplos documentados, no una descripción universal."
        ),
    },
    {
        "number": 10,
        "title": "Problemáticas y desafíos actuales",
        "lead": "Protección del territorio, espacios sagrados y afectaciones ambientales.",
        "body": (
            "Entre los desafíos documentados están la protección del territorio ancestral, las "
            "presiones sobre los espacios sagrados, los conflictos territoriales y las afectaciones "
            "ambientales, incluida la deforestación y la quema de bosques.\n\n"
            "El Centro Nacional de Memoria Histórica documenta hechos de violencia contra líderes "
            "Arhuacos, entre ellos el caso de Ángel María Torres, Hugues Chaparro y Luis Napoleón "
            "Torres, desaparecidos, torturados y asesinados el 28 de noviembre de 1990.\n\n"
            "El documental «Voces de las montañas sagradas» (2018) aborda la defensa del territorio "
            "frente a presiones asociadas con proyectos mineros, en el contexto documentado ese año."
        ),
        "care_note": (
            "Estos desafíos no definen por completo al pueblo Arhuaco: también existen procesos de "
            "organización, resistencia, creación cultural y participación comunitaria."
        ),
    },
    {
        "number": 11,
        "title": "Los Arhuacos en la actualidad",
        "lead": "Procesos organizativos, derechos colectivos e interlocución con instituciones.",
        "body": (
            "Los procesos de resistencia cultural incluyen la defensa del territorio, el "
            "fortalecimiento de la lengua, la educación propia y la transmisión de conocimientos. "
            "La cultura Arhuaca es viva y continúa transformándose en relación con las decisiones de "
            "sus comunidades.\n\n"
            "El Decreto 0514 de 2026 precisa el territorio ancestral de los cuatro pueblos de la "
            "Sierra Nevada y el sistema de espacios sagrados de la Línea Negra.\n\n"
            "Existen producciones audiovisuales construidas con participación de autoridades y "
            "comunidades tradicionales; el archivo las considera recursos de consulta respetando "
            "créditos, contexto y condiciones de uso."
        ),
        "care_note": "",
    },
    {
        "number": 12,
        "title": "Galería multimedia",
        "lead": "Materiales visuales y sonoros del territorio, la memoria y las expresiones culturales.",
        "body": (
            "Esta sección reúne materiales cuya procedencia, créditos y permisos de uso han sido "
            "verificados. Fotografías de la Sierra Nevada, tejidos y mochilas, videos y testimonios, "
            "y mapas de ubicación general."
        ),
        "care_note": (
            "No se publican imágenes, audios o videos de carácter reservado. Cada material lleva "
            "lugar general, autoría y fecha cuando se conocen."
        ),
    },
    {
        "number": 13,
        "title": "Fuentes de información",
        "lead": "Instituciones públicas, organizaciones indígenas y repositorios académicos.",
        "body": (
            "Las referencias deben consultarse nuevamente antes de publicar contenidos, "
            "especialmente cuando se incorporen datos sensibles, cifras demográficas o contenidos "
            "sujetos a cambios normativos."
        ),
        "care_note": (
            "Nota metodológica: este archivo no sustituye la consulta directa con el pueblo Arhuaco "
            "ni la revisión de sus autoridades. La inteligencia artificial opera únicamente sobre "
            "contenidos cuyo uso haya sido permitido."
        ),
    },
]

# clave -> (tipo, referencia, url, año). La clave sirve para vincular cada
# fuente con las secciones que la citan (ver SECTION_SOURCES).
SOURCES = {
    "mincultura": ("institucional", "Ministerio de Cultura. (s. f.). Iku (Arhuacos): Guardianes de la vida. Caracterizaciones de los pueblos indígenas de Colombia.", "https://mng.mincultura.gov.co/prensa/noticias/Documents/Poblaciones/archuaco.pdf", ""),
    "onic": ("organizacion", "Organización Nacional Indígena de Colombia (ONIC). (s. f.). Ijku – Arhuaco.", "https://www.onic.org.co/pueblos/110-arhuaco", ""),
    "procuraduria": ("institucional", "Procuraduría General de la Nación. (s. f.). Caracterización general de la comunidad pueblo indígena Arhuaco.", "https://www.procuraduria.gov.co/portal/media/docs/Caracterizacionarhuaco.pdf", ""),
    "icanh": ("academica", "Instituto Colombiano de Antropología e Historia (ICANH). (s. f.). Pueblo Arhuaco.", "https://colecciones.icanh.gov.co/articulos/pueblos/ARHUACO.php", ""),
    "pes": ("institucional", "Ministerio de Cultura y Consejo Territorial de Cabildos Gobernadores de la Sierra Nevada de Santa Marta. (2016). Plan Especial de Salvaguardia: Sistema de conocimiento ancestral de los cuatro pueblos indígenas de la Sierra Nevada de Santa Marta.", "https://mincultura.gov.co/direcciones/patrimonio-y-memoria/Documents/21-sistema-de-conocimiento-ancestral-SNSM-PES.pdf", "2016"),
    "unad": ("academica", "Hernández Montes, N. E. (2017). Las tradiciones orales como proceso de enseñanza y de aprendizaje para el fortalecimiento de las tradiciones culturales Arhuacas. Universidad Nacional Abierta y a Distancia.", "https://repository.unad.edu.co/handle/10596/13937", "2017"),
    "cnmh": ("institucional", "Centro Nacional de Memoria Histórica. (s. f.). Memorias Étnicas: Pueblo Arhuaco.", "https://centrodememoriahistorica.gov.co/micrositios/comunidades-etnicas/maleta.html", ""),
    "decreto": ("norma", "República de Colombia, Ministerio del Interior. (2026, 19 de mayo). Decreto 0514 de 2026.", "https://jurinfo.jep.gov.co/Normograma/compilacion/docs/decreto_0514_2026.htm", "2026"),
    "magdalena": ("institucional", "Gobernación del Magdalena. (s. f.). Información sobre grupos indígenas.", "https://www.gobernaciondelmagdalena.gov.co/transparencia-resolucion-1519-de-2020/transparencia-informacion-especifica-para-grupos-de-interes/grupos-indigenas/", ""),
    "ant": ("institucional", "Agencia Nacional de Tierras. (s. f.). Pueblo Arhuaco recibe 465 hectáreas para ampliar su territorio ancestral.", "https://www.ant.gov.co/prensa/noticias/con-el-fin-de-que-amplien-su-territorio-ancestral-pueblo-arhuaco-recibe-de-la-ant-un-total-de-465-hectareas", ""),
    "iwgia": ("audiovisual", "IWGIA, Ore Media y Canejo Producciones. (2018). Voces de las montañas sagradas – Pueblo Arhuaco [Documental]. YouTube.", "https://www.youtube.com/watch?v=BEp8V93WlKs", "2018"),
    "dw": ("audiovisual", "DW Español. (2019, 13 de marzo). La resiliencia del pueblo arhuaco en Colombia [Video]. YouTube.", "https://www.youtube.com/watch?v=TF6xNDoiNJM", "2019"),
    "rosario": ("audiovisual", "Universidad del Rosario. (2023, 13 de febrero). Mamü, máxima autoridad política y espiritual de la comunidad arhuaca [Video]. YouTube.", "https://www.youtube.com/watch?v=FxUZuRzcoJU", "2023"),
    "pnn": ("fotografica", "Parques Nacionales Naturales de Colombia. (s. f.). Parque Nacional Natural Sierra Nevada de Santa Marta.", "https://www.parquesnacionales.gov.co/nuestros-parques/pnn-sierra-nevada-de-santa-marta/", ""),
    "eltiempo": ("fotografica", "EL TIEMPO. (2022). Mujeres indígenas: Crónicas de la Sierra Nevada.", "https://www.eltiempo.com/infografias/2022/10/mujeres_indigenas/cronicas-dev/sierra/index.html", "2022"),
    "artesanias": ("fotografica", "Artesanías de Colombia. (s. f.). Jóvenes artesanos Arhuacos impulsan iniciativa de desarrollo artesanal. Sistema de Información para la Artesanía (SIART).", "https://artesaniasdecolombia.com.co/PortalAC/Noticia/jovenes-artesanos-arhuacos-impulsan-iniciativa-de-desarrollo-artesanal_3482", ""),
}

# Las figuras del documento base: número de sección -> (figura, título, nota, archivo).
# Se sirven como estáticos del front (`public/figuras/`) y no desde MEDIA_ROOT,
# que en Vercel es efímero. Cada una conserva su crédito completo.
FIGURES = {
    1: [
        (2, "Población Arhuaca reunida",
         "Fotografía de Óscar Pérez, publicada en ¿Qué está pasando con el Pueblo Arhuaco "
         "en el Cesar?, por Redacción Colombia (2022), El Espectador.",
         "/figuras/poblacion-reunida.jpg"),
    ],
    2: [
        (1, "Hombres Arhuacos",
         "Fotografía de Raúl Arboleda, publicada por AFP en NAIZ (2024).",
         "/figuras/hombres-arhuacos.jpg"),
    ],
    3: [
        (3, "Mapa de resguardos indígenas y figuras ambientales de la Sierra Nevada de Santa Marta",
         "Mapa de delimitación de resguardos indígenas, reservas forestales, parques "
         "nacionales naturales y corporaciones autónomas regionales. Fuente temática: "
         "Consejo Territorial de Cabildos de la Sierra Nevada de Santa Marta (2015); "
         "base cartográfica: Instituto Geográfico Agustín Codazzi (IGAC).",
         "/mapa-resguardos-snsm.jpg"),
        (14, "Departamentos y municipios de mayor concentración del pueblo Arhuaco",
         "Mapa tomado de Arhuacos: Los guardianes de la vida, por Carlos Garizabalo Hoyos "
         "(s. f.), Casa Chünü'ü. Fuente cartográfica: Cartografía de la Diversidad – "
         "Dirección de Poblaciones; fuente estadística: Censo DANE 2005.",
         "/figuras/mapa-departamentos.jpg"),
    ],
    5: [
        (4, "Mamü, autoridad espiritual y política del pueblo Arhuaco",
         "Captura de pantalla del video Mamü, máxima autoridad política y espiritual de la "
         "comunidad arhuaca, publicado por la Universidad del Rosario (2023).",
         "/figuras/mamu-autoridad.jpg"),
    ],
    6: [
        (5, "Vestimenta tradicional Arhuaca",
         "Fotografía de Juan Arboleda, publicada en Fotocommunity.",
         "/figuras/vestimenta-tradicional.jpg"),
        (6, "Práctica del tejido Arhuaco",
         "Fotografía tomada de Mujeres indígenas, por EL TIEMPO (2022).",
         "/figuras/practica-tejido.jpg"),
        (7, "Práctica ceremonial del pueblo Arhuaco",
         "Fotografía publicada en Etnias del Mundo (s. f.).",
         "/figuras/practica-ceremonial.jpg"),
    ],
    9: [
        (8, "Recolección de caña de azúcar por integrantes del pueblo Arhuaco",
         "Fotografía de Laura Rodríguez Navarro, publicada por la Oficina de las Naciones "
         "Unidas contra la Droga y el Delito (UNODC), en Noticias ONU (2021).",
         "/figuras/labores-agricolas.jpg"),
        (9, "Artesanas Arhuacas participan en un taller sobre la calidad de la lana",
         "Fotografía publicada por AGROSAVIA (2025), en el marco de un taller sobre la "
         "calidad de la lana y el tejido tradicional en Nabusímake.",
         "/figuras/taller-lana.jpg"),
    ],
    12: [
        (10, "Sierra Nevada de Santa Marta",
         "Imagen tomada de Parque Nacional Natural Sierra Nevada de Santa Marta, por "
         "Colombia País (s. f.).",
         "/figuras/sierra-nevada.jpg"),
        (11, "Paisaje de la Sierra Nevada de Santa Marta",
         "Fotografía tomada de Parque Nacional Natural Sierra Nevada de Santa Marta, por "
         "Parques Nacionales Naturales de Colombia (s. f.).",
         "/figuras/sierra-nevada-paisaje.jpg"),
        (12, "Mochila tradicional del pueblo Arhuaco",
         "Fotografía tomada de Jóvenes artesanos Arhuacos impulsan iniciativa de desarrollo "
         "artesanal, por SIART (2012), Artesanías de Colombia.",
         "/figuras/mochila-tradicional.jpg"),
        (13, "Registro audiovisual relacionado con el pueblo Arhuaco",
         "Captura de pantalla tomada del video publicado en YouTube (Noticias Caracol, 2025).",
         "/figuras/registro-audiovisual.jpg"),
    ],
}

# Las líneas «Fuente de apoyo» del documento base, sección por sección.
SECTION_SOURCES = {
    2: ["mincultura", "onic", "procuraduria"],
    3: ["procuraduria", "mincultura", "decreto", "ant"],
    4: ["procuraduria", "icanh", "decreto"],
    5: ["onic", "mincultura", "unad", "rosario"],
    6: ["mincultura", "icanh", "procuraduria", "eltiempo", "artesanias"],
    7: ["pes", "icanh", "decreto"],
    8: ["unad", "pes"],
    9: ["pes", "onic", "magdalena"],
    10: ["icanh", "cnmh", "unad", "iwgia", "dw"],
    11: ["mincultura", "cnmh", "decreto", "iwgia"],
    12: ["pnn", "eltiempo", "artesanias", "rosario"],
    13: list(SOURCES),  # la sección de fuentes las reúne todas
}


class Command(BaseCommand):
    help = "Siembra las secciones del archivo y las fuentes del documento base."

    @transaction.atomic
    def handle(self, *args, **options):
        sections: dict[int, ArchiveSection] = {}
        for data in SECTIONS:
            section, created = ArchiveSection.objects.update_or_create(
                number=data["number"],
                defaults={
                    "title": data["title"],
                    "lead": data["lead"],
                    "body": data["body"],
                    "care_note": data["care_note"],
                    "is_published": True,
                },
            )
            sections[section.number] = section
            self.stdout.write(
                f"{'+' if created else '·'} {section.number}. {section.title}"
            )

        figuras = 0
        for number, items in FIGURES.items():
            section = sections.get(number)
            if section is None:
                continue
            for order, (figura, caption, note, url) in enumerate(items):
                Figure.objects.update_or_create(
                    section=section,
                    number=figura,
                    defaults={
                        "caption": caption,
                        "note": note,
                        "external_url": url,
                        "order": order,
                    },
                )
                figuras += 1

        sources: dict[str, Source] = {}
        for key, (kind, citation, url, year) in SOURCES.items():
            source, _ = Source.objects.update_or_create(
                citation=citation,
                defaults={"kind": kind, "url": url, "year": year},
            )
            sources[key] = source

        # Vincula cada fuente con las secciones que la citan, según las líneas
        # «Fuente de apoyo» del documento base.
        enlaces = 0
        for number, keys in SECTION_SOURCES.items():
            section = sections.get(number)
            if section is None:
                continue
            section.sources.set([sources[key] for key in keys])
            enlaces += len(keys)

        self.stdout.write(
            self.style.SUCCESS(
                f"Listo: {len(SECTIONS)} secciones, {figuras} figuras, "
                f"{len(SOURCES)} fuentes y {enlaces} vínculos."
            )
        )
