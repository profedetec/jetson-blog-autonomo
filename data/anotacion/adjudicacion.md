# Adjudicación — fase de consenso (propuesta 2026-10-16, decidida por el autor 2026-10-19)

Las etiquetas ciegas del autor en `para_autor/anotacion_autor.xlsx` NO se modifican;
esta tabla es la propuesta de consenso; ver la decisión del autor al final.

## Acuerdo crudo (87 afirmaciones comparadas, 1 marcada NA por el autor)

| Esquema | Acuerdo | Kappa de Cohen | Gwet AC1 | PABAK |
|---|---|---|---|---|
| 6 etiquetas | 82.8 % | 0.156 | 0.820 | 0.793 |
| 3 grupos (correcta / error / no verificable) | 95.4 % | 0.481 | 0.952 | 0.931 |

Kappa bajo por paradoja de prevalencia (R = 85–93 % en ambos anotadores).

## Desacuerdos y propuesta

| Art. #  | Claude | Autor | Consenso propuesto | Motivo (verificado contra el texto fuente) |
|---|---|---|---|---|
| A02 #2  | R  | EC | **R**  | F1: "@ServeTheHome takes a deep dive into AMD Instinct MI455X". Está en la fuente. |
| A02 #4  | R  | NA | **R**  | F1: "exploring the … rack-scale advances". Es verificable y está en la fuente. |
| A02 #7  | R  | EC | **R**  | F3: "NVIDIA Vera Rubin is ramping into full production". |
| A02 #8  | R  | EC | **R**  | F3: "Congrats to the teams at @Microsoft…" (el propio comentario del autor cita el tuit). |
| A07 #2  | D  | R  | **D** (a discutir) | "New Fellows Research:" = nueva investigación de los Fellows; el artículo lo vuelve nombre de programa. Distorsión menor de atribución. |
| A07 #7  | EC | R  | **EC** | "Claude es un modelo de Anthropic" no está en los tuits → externa (PROTOCOLO.md). |
| A07 #10 | EC | R  | **EC** | Explicación de qué es un static fire: conocimiento general, no está en F2. |
| A20 #2  | D  | R  | **D**  | Fuente: "90%+ of my **miles**"; artículo: "90 % de sus **trayectos**". Cambio de unidad/alcance. |
| A28 #3  | R  | EN | **D**  | Fuente: "~8:34 a.m. PT"; el artículo (l. 33) dice "**a las** 8:34", quita el "aprox." — análogo a "más de 20 %" → "20 %". El autor tiene razón en que hay un problema; Claude se equivocó al marcar R y al parafrasear la afirmación como "hacia las". EN no aplica (el dato sí está en la fuente). |
| A29 #8  | EC | R  | **EC** | Qué hace una quema de desorbitación: no está en F2. |
| A29 #9  | EC | R  | **EC** | Qué lleva el tronco de Dragon: no está en F2. |
| A30 #2  | EC | R  | **EC** | Los tuits solo dan el handle @SemperCitiusSDA; que sea la Space Development Agency es externo. |
| A30 #7  | EC | R  | **EC** | Definición de carga de propelente: conocimiento general. |
| A30 #8  | D  | R  | **D**  | El artículo (l. 34) dice que el tuit "Watch Falcon 9 launch…" (F1) confirmó el lanzamiento; es una invitación a ver la transmisión. |
| A30 #11 | EC | R  | **EC** | No está en las fuentes. |
| A30 #12 | EC | R  | **EC** | No está en las fuentes. |

Patrón principal: 8 de 15 desacuerdos son conocimiento general verdadero que el autor
etiquetó R; el protocolo exige EC cuando el dato no está en los 3 tuits. Inverso en
A02 #2/#7/#8 (dato en la fuente que el autor marcó EC tras verificarlo fuera).

## Otras observaciones

- A01 #1: ambos D, pero el comentario del autor ("El artículo dice más del 20 %") está
  invertido: la **fuente** dice "over 20%" y el **artículo** "del 20 %".
- A02 #9 (Vera Rubin "para aplicaciones astronómicas"): ambos EI. Alucinación confirmada.
- Hoja "Faltantes": el autor no agregó afirmaciones → acuerdo total en la segmentación.
- A28 #3: corregida en `anotaciones_claude.json` (R → D, texto de la afirmación) el 2026-10-16 tras aprobación del autor; métricas recalculadas.

## Decisión del autor (2026-10-19)

El autor revisó las 15 filas de desacuerdo y la afirmación A02 #4 (marcada NA), cada una
con el texto de la fuente y la nota de Claude, y aceptó todas las propuestas de consenso
de esta tabla conforme a PROTOCOLO.md. A07 #2 queda en **D** (distorsión menor de nombre).
Las etiquetas de consenso de `anotaciones_claude.json` no cambian: la única modificación
respecto a las etiquetas ciegas de Claude sigue siendo A28 #3 (R → D).
