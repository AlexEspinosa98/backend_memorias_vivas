# Propuesta de inteligencia artificial para Memorias Vivas

Proyecto ALUNA IA · Universidad del Magdalena
Versión 1 — 25 de noviembre de 2026

---

## 1. De qué parte esta propuesta

La plataforma ya está construida: muro con historias, comunidades, cuatro
niveles de visibilidad, registro obligatorio de autorización, marcado de
contenido sensible, comentarios, aprecios, visitas, promociones, mapa y las 13
secciones del archivo.

El documento base del proyecto dice dos cosas sobre la IA, y las dos son
límites antes que funciones:

> Sus funciones de inteligencia artificial podrán facilitar la transcripción de
> audios, la clasificación de materiales y la búsqueda de contenidos
> registrados. La tecnología no reemplaza la voz de los mayores ni la autoridad
> de la comunidad sobre sus conocimientos.

> La inteligencia artificial debe operar únicamente sobre contenidos cuyo uso
> haya sido permitido.

Esta propuesta toma esa frase como requisito técnico, no como advertencia. Todo
lo que sigue está pensado para correr **dentro** del modelo de permisos que ya
existe en el código.

---

## 2. Cinco reglas que toda función de IA debe cumplir

Antes del catálogo de funciones, los invariantes. Conviene implementarlos una
sola vez, en una capa `ai/` compartida, y que ninguna función los pueda saltar.

| # | Regla | Cómo se verifica en el código |
| --- | --- | --- |
| 1 | **Solo contenido autorizado.** Ningún modelo lee una historia sin `Consent`. | La capa de IA consulta por `Story.objects.filter(consents__isnull=False)`; nunca por `Story.objects.all()`. |
| 2 | **El alcance del consentimiento manda.** Un `Consent` con alcance `consulta` no alimenta búsqueda pública ni recomendaciones. | El índice guarda `scope` y `visibility`; toda consulta filtra por el permiso de quien pregunta, igual que `StoryQuerySet.visible_for`. |
| 3 | **Lo sensible no sale.** `is_sensitive=True` queda fuera de índices, resúmenes y sugerencias. | Mismo filtro que ya excluye estas historias del endpoint `/historias/mapa/`. |
| 4 | **Nada se publica solo.** La IA propone; una persona de la comunidad acepta. | Toda salida se guarda como sugerencia con estado `pendiente`, nunca escribe en `Story.body`, `Story.tags` ni `MediaItem.transcript` directamente. |
| 5 | **Nada entrena modelos externos.** Los contenidos no se usan para entrenar ni se envían a proveedores que los retengan. | Modelos locales donde se pueda; donde no, proveedor con retención cero y registro de cada envío. |

A esto se añade una regla de gobierno: **cada comunidad puede apagar cualquier
función de IA sobre sus contenidos**. En el modelo de datos sería un campo
`ai_settings` (JSON) en `Community`, con el valor por defecto en «desactivado»
hasta que la comunidad lo active.

---

## 3. Las funciones propuestas

### 3.1 Transcripción asistida de audio — *alta prioridad*

**Problema.** El archivo vive de testimonios grabados. Transcribir a mano ocho
minutos de audio toma cerca de una hora.

**Propuesta.** Whisper (large-v3) corriendo en el servidor del proyecto, no en
un servicio externo. Produce un borrador con marcas de tiempo que llena
`MediaItem.transcript` **en estado de borrador**, visible solo para la autoría
y la autoridad de la comunidad. La historia no se puede publicar mientras la
transcripción esté sin revisar.

**El punto difícil: la lengua Ika.** Whisper no soporta Ika, y ningún modelo
comercial lo hace. Conviene ser honesto sobre esto en el documento del proyecto:

- Para audio en español, la transcripción automática funciona bien hoy.
- Para audio en Ika, la propuesta realista es un **alineador**, no un
  transcriptor: la comunidad escribe la transcripción y el sistema la alinea
  con el audio para poder saltar a cada fragmento. Eso ya es útil y no inventa
  nada.
- A mediano plazo, con suficientes pares audio–texto en Ika autorizados por la
  comunidad (del orden de 20–40 horas), se puede ajustar un modelo propio. Ese
  corpus es patrimonio de la comunidad y el acuerdo sobre su propiedad debería
  firmarse antes de empezar a reunirlo.

**Dónde entra en lo ya construido:** `MediaItem.transcript`, que hoy está vacío
y documentado como «transcripción revisada por la comunidad».

---

### 3.2 Búsqueda semántica sobre el archivo — *alta prioridad*

**Problema.** La búsqueda actual es por coincidencia de texto. Quien busca
«cómo se aprende a tejer» no encuentra un relato titulado «El pensamiento de la
mochila».

**Propuesta.** Embeddings multilingües (`multilingual-e5-large`, que corre en
local) sobre título, resumen, cuerpo y transcripciones revisadas. Se guardan en
Postgres con `pgvector` — la misma base que ya usa el proyecto, sin
infraestructura nueva.

**La parte crítica es el filtro.** El índice vectorial debe guardar, junto al
embedding, el `visibility`, el `community_id` y el `scope` del consentimiento.
La consulta filtra **antes** de calcular similitud, no después: si se filtra
después, los resultados descartados ya revelaron que existen.

```python
# stories/ai/search.py  (esbozo)
def buscar(consulta: str, user) -> list[Story]:
    vector = embed(consulta)
    permitidas = Story.objects.visible_for(user).filter(
        is_sensitive=False,
        consents__scope__in=[Consent.Scope.OPEN, Consent.Scope.COMMUNITY],
    )
    return (
        StoryEmbedding.objects
        .filter(story__in=permitidas)
        .order_by(CosineDistance("vector", vector))[:20]
    )
```

---

### 3.3 Revisor de cuidado cultural — *la función más valiosa del proyecto*

**Problema.** El riesgo real del archivo no es técnico: es que alguien publique
de buena fe algo que no debía salir. Un sitio sagrado nombrado al pasar, una
práctica de pagamento descrita, la voz de un mayor que no dio permiso.

**Propuesta.** Un revisor que corre **antes** de que la historia llegue a la
cola de revisión, y que no bloquea: marca y explica. Combina dos capas:

1. **Reglas explícitas**, construidas con la comunidad: una lista de términos y
   lugares que exigen revisión de autoridad. Esta lista es de la comunidad, se
   edita desde el admin y no se publica.
2. **Un modelo de lenguaje** con un prompt acotado que responde tres preguntas:
   ¿menciona un lugar sagrado o un sitio que podría serlo? ¿describe una
   práctica ceremonial? ¿atribuye palabras a una persona identificable?

La salida no es un veredicto: es una nota para la autoridad que revisa, del
tipo «este texto menciona un lugar y una práctica ceremonial; conviene
verificar con la autoridad antes de publicar». Quien decide sigue siendo la
persona.

**Dónde entra:** un campo `ai_review_notes` en `Story`, mostrado en
`/revision` junto a la autorización. Impacto inmediato en la calidad del
cuidado, y es lo que distingue este proyecto de un muro social cualquiera.

---

### 3.4 Sugerencias de catalogación — *prioridad media*

Al guardar un borrador, el sistema propone: tipo de contenido, etiquetas,
lugar mencionado, resumen de dos líneas y una ficha de crédito en el formato
que ya usa el archivo («Nota. Fotografía de…, publicada en…»).

Todo llega como **sugerencia editable**, nunca aplicado. Reduce el trabajo de
catalogación, que es lo que hace que los archivos comunitarios se abandonen a
los seis meses.

---

### 3.5 Recomendaciones en el muro — *prioridad media*

Tres usos, por orden de utilidad real:

- **«Historias relacionadas»** al pie de cada detalle, por similitud semántica
  dentro de lo que esa persona puede ver.
- **«Memorias que se conectan»**: cuando dos comunidades tienen relatos sobre
  el mismo tema (el tejido, el café, la educación propia), proponerle a cada
  autoridad que vea la del otro. Esto teje el archivo entre comunidades, que es
  justo lo que un archivo disperso no logra.
- **«Esto falta»**: comparar lo que hay con las 13 secciones del archivo y
  señalar vacíos («la sección de lengua tiene un solo registro en Ika»). Sirve
  para orientar el trabajo de campo.

Nunca un ranking por popularidad: en un archivo de memoria, lo más visto no es
lo más importante.

---

### 3.6 Asistente de consulta del archivo (RAG) — *prioridad media, con cuidado*

Un buscador conversacional sobre las 13 secciones y las historias de uso
abierto, pensado para las nuevas generaciones y para visitantes.

Condiciones no negociables:

- Responde **solo** con lo que está en el archivo autorizado. Si no está, dice
  que no está, en vez de completar con lo que el modelo sabe del pueblo
  Arhuaco por internet.
- **Cita siempre** la sección o la historia, con enlace.
- No responde sobre cosmovisión, Ley de Origen, pagamentos ni sitios sagrados:
  devuelve la nota de cuidado cultural de la sección 7 y remite a las
  autoridades. Esto se implementa como una lista de temas vedados revisada por
  la comunidad, no como criterio del modelo.
- Cada conversación queda registrada para que la comunidad pueda auditar qué
  está respondiendo el sistema en su nombre.

---

### 3.7 Accesibilidad y lengua — *prioridad baja, alto valor simbólico*

- Subtítulos automáticos en video (misma cadena que 3.1).
- Descripciones alternativas sugeridas para las fotografías, revisadas por quien
  publica.
- Lectura en voz alta de los relatos en español, para quienes leen poco.
- **Glosario Ika comunitario**: no traducción automática, sino un diccionario
  que la comunidad llena y que el sistema usa para enlazar palabras en los
  textos. Es la forma de apoyar la lengua sin que una máquina decida qué
  significan las palabras.

---

## 4. Prioridades y esfuerzo

| Función | Valor | Esfuerzo | Riesgo cultural | Cuándo |
| --- | --- | --- | --- | --- |
| 3.3 Revisor de cuidado cultural | Muy alto | Medio | Bajo (asiste, no decide) | Fase 1 |
| 3.1 Transcripción (español) | Muy alto | Medio | Medio (exige revisión) | Fase 1 |
| 3.2 Búsqueda semántica | Alto | Medio | Bajo si el filtro es correcto | Fase 1 |
| 3.4 Catalogación sugerida | Alto | Bajo | Bajo | Fase 2 |
| 3.5 Recomendaciones | Medio | Bajo | Medio (puede cruzar permisos) | Fase 2 |
| 3.6 Asistente RAG | Medio | Alto | **Alto** | Fase 3 |
| 3.7 Accesibilidad y glosario | Medio | Medio | Bajo | Fase 3 |
| 3.1 Alineación / ASR en Ika | Alto | Muy alto | Alto (corpus comunitario) | Fase 4, con acuerdo previo |

**Fase 1** es lo que haría una diferencia visible en un prototipo de tesis: el
revisor de cuidado cultural y la transcripción en español, con búsqueda
semántica encima. Las tres caben en el modelo de datos actual sin rediseñarlo.

---

## 5. Cómo encaja técnicamente

```
backend_memorias_vivas/
  ai/
    __init__.py
    guards.py        las cinco reglas de la sección 2, en un solo lugar
    embeddings.py    multilingual-e5-large → pgvector
    transcribe.py    Whisper large-v3, cola de trabajos
    review.py        revisor de cuidado cultural (reglas + modelo)
    suggest.py       catalogación y recomendaciones
    models.py        AiSuggestion, StoryEmbedding, AiAuditLog
```

- **`AiSuggestion`**: toda salida de IA vive aquí con `story`, `kind`,
  `payload`, `status` (`pendiente` / `aceptada` / `descartada`) y quién decidió.
  Nunca se escribe directo sobre `Story`.
- **`AiAuditLog`**: qué modelo, sobre qué contenido, en qué momento y a pedido
  de quién. Es lo que permite responderle a una comunidad qué hizo el sistema
  con sus materiales.
- **Modelos locales donde se pueda.** Whisper y los embeddings corren en una
  máquina del proyecto. Esto importa más de lo que parece: enviar la voz de un
  mayor a un servidor ajeno es, en los términos del documento base, divulgar un
  contenido.
- **Vercel no sirve para esto.** Las funciones serverless tienen límite de
  tiempo y no tienen GPU. La transcripción y los embeddings necesitan un
  servidor aparte (una máquina de la universidad, o un contenedor en Railway o
  Fly.io) con una cola de trabajos. El muro puede seguir en Vercel.

---

## 6. Lo que esta propuesta recomienda **no** hacer

Vale la pena dejarlo escrito, porque son las funciones que primero se le ocurren
a cualquiera:

- **Traducción automática español ↔ Ika.** No hay datos suficientes y el costo
  de un error es alto: una traducción equivocada de un término ceremonial
  circula después como si fuera cierta.
- **Generación de contenido cultural.** Que el sistema «complete» un relato o
  «redacte» una descripción de una práctica contradice el propósito del
  archivo. La IA reorganiza y busca; no narra.
- **Reconocimiento facial** en las fotografías, aunque sirviera para organizar
  la galería.
- **Moderación automática de comentarios.** Puede señalar, pero no ocultar: ya
  existe `Comment.is_hidden` con decisión humana y motivo registrado.
- **Entrenar cualquier modelo con los contenidos del archivo** sin un acuerdo
  escrito y específico sobre la propiedad del corpus resultante.

---

## 7. Lo primero que habría que hacer

Antes de escribir una línea de código de IA: **llevar esta propuesta a las
autoridades de las comunidades participantes** y acordar, para cada función,
si la quieren, sobre qué contenidos y quién revisa. El documento base lo dice
con claridad y aquí aplica entero: la tecnología no reemplaza la autoridad de
la comunidad sobre sus conocimientos.

Un orden posible para esa conversación:

1. Mostrar la plataforma funcionando, sin IA. Que se vea el control que ya
   tienen sobre la visibilidad y la autorización.
2. Proponer el revisor de cuidado cultural (3.3) como primera función, porque
   es la que trabaja a favor de lo que a ellos les preocupa.
3. Proponer la transcripción (3.1) como segunda, porque es la que les ahorra
   trabajo.
4. Dejar el resto para cuando haya confianza en las dos primeras.
