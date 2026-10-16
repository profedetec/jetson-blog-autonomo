# Protocolo de anotación de exactitud factual (v1, 2026-10-14)

**Unidad:** afirmación factual atómica = un enunciado verificable sobre el mundo
(quién, qué, cuánto, cuándo, dónde). Una oración con dos datos verificables son
dos afirmaciones.

**No se anotan:** opiniones, valoraciones o especulación marcada como tal
("podría", "sugiere", "es probable"), generalidades sin contenido verificable
("la IA avanza rápidamente"), el título, la sección de Referencias (la genera
el código) y la ficha de autor. Tampoco las meta-afirmaciones sobre lo que la fuente
**omite** ("no se especifican detalles…", "el anuncio no menciona…").

**Fuentes válidas:** el texto de los 3 tuits **y** los datos que el sistema
entrega al modelo junto con ellos: métricas de engagement (me gusta,
respuestas, retuits), fecha, cuenta y enlaces a documentos oficiales. Las
métricas se verifican contra la última medición de la base anterior a la
publicación (`metricas.py`). Si el tuit está truncado en la base, cuenta solo
lo visible.

**Etiquetas** (comparando con el texto de las 3 fuentes del artículo):

| Código | Etiqueta | Criterio |
|---|---|---|
| R | Respaldada | La fuente la dice o se sigue directamente de ella. Paráfrasis fiel incluida. |
| D | Distorsionada | Basada en la fuente pero con un cambio de alcance, cifra, matiz o atribución ("más de 20 %" → "20 %"). |
| C | Contradice | Afirma lo contrario de la fuente. |
| EC | Externa correcta | No está en las fuentes; es verdadera según conocimiento verificable. |
| EI | Externa incorrecta | No está en las fuentes; es falsa. |
| EN | Externa no verificable | No está en las fuentes y no se puede comprobar con razonable seguridad. |

**Métricas:** por artículo, nº de afirmaciones y proporción de cada etiqueta;
tasa de fidelidad = R / total; tasa de error = (D + C + EI) / total;
tasa de conocimiento externo = (EC + EI + EN) / total.

**Acuerdo entre anotadores:** 10 artículos (subconjunto fijo, semilla 20261015)
los anota el autor de forma independiente, sin ver las etiquetas del otro
anotador. Se reporta kappa de Cohen sobre las afirmaciones comunes y el
acuerdo en el número de afirmaciones por artículo.
