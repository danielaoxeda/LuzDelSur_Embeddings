# Prueba con semillas demo del backend

- Fecha: 2026-11-17
- Modelo: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- Umbrales evaluados: 0.55 (coincidencia) y 0.30 (conflicto), los actuales del backend
- Fuente de datos: `DemoDataSeeder.java` de la rama `develop` del backend
- Script: `scripts/probar_con_semillas.py`
- Entrada: `scripts/datos/semillas_backend.csv`
- Pares exportados: `docs/prueba_semillas_pares.csv`

> **Aviso.** Las descripciones y las etiquetas salen de los comentarios del
> `DemoDataSeeder`, escritos por el mismo equipo que redactó las descripciones.
> Esto es una **prueba de humo**, no una validación independiente. Los datos no
> son reportes reales y no se usaron para calibrar ni para cambiar umbrales.

## 1. Objetivo y alcance

Comprobar, como señal auxiliar, qué similitud produce el modelo con las
descripciones demo que el equipo del backend agregó en `develop`. No se modificó
el backend, no se cambiaron umbrales y no se usó esta muestra para calibrar.

La similitud **no decide sola**: el motor de reglas del backend filtra por
sector, ventana temporal y tipo de falla, y usa la similitud solo como señal de
certeza. Esta prueba aísla la señal semántica para ver qué aporta.

## 2. Origen de los datos (solo lectura)

No hay seeds de reportes en Flyway: `V1`–`V5` solo definen esquema (usuarios,
auditoría, historial y feedback). Los 15 reportes demo se crean en
`backend/src/main/java/.../config/DemoDataSeeder.java`, pasando por
`ReportService` y `IncidentService` (no insertan SQL directo).

Los comentarios del seeder describen tres casos ya confirmados y los escenarios
C1–C5. **No existe un campo `incidente_esperado` ni un ID de incidente en los
datos.** Las etiquetas de este informe se derivaron de esos comentarios y del
flujo del seeder (`confirm`, `assignTechnician`, `changeStatus`); no son una
verdad de campo.

| ID | Sector | Tipo | Descripción | Etiqueta |
| --- | --- | --- | --- | --- |
| R01 | San Borja | BAJA_TENSION | Los focos estan muy bajos y la refrigeradora se apaga sola | SAN_BORJA |
| R02 | San Borja | BAJA_TENSION | Baja tension en toda la cuadra, los equipos no encienden | SAN_BORJA |
| R03 | Chorrillos | ALUMBRADO_PUBLICO | Los postes de la avenida estan apagados toda la noche | |
| R04 | Lince | CORTE_TOTAL | Se fue la luz en toda la manzana despues de un chispazo | LINCE |
| R05 | Lince | CORTE_TOTAL | Corte de energia en el edificio y en los vecinos | LINCE |
| R06 | San Isidro | CORTE_TOTAL | No hay luz en toda la cuadra desde hace 20 minutos | SAN_ISIDRO_C1 |
| R07 | San Isidro | CORTE_TOTAL | Corte de energia en mi casa y en la de los vecinos | SAN_ISIDRO_C1 |
| R08 | san isidro | CORTE_TOTAL | Se fue la electricidad en la zona | SAN_ISIDRO_C1 |
| R09 | Barranco | CORTE_TOTAL | Corte total de energia en la calle | |
| R10 | Barranco | BAJA_TENSION | La tension baja y los focos parpadean | |
| R11 | Miraflores | INTERMITENCIA | La luz se corta cada diez minutos | MIRAFLORES_C3_1 |
| R12 | Miraflores | INTERMITENCIA | Microcortes continuos en el departamento | MIRAFLORES_C3_2 |
| R13 | Santiago de Surco | CORTE_TOTAL | Apagon en la urbanizacion | |
| R14 | Surquillo | CORTE_TOTAL | Sin energia en los comercios de la avenida | |
| R15 | (sin sector) | MEDIDOR | El medidor hace ruido y huele a quemado | |

Cómo se relacionan con incidentes, según el seeder:

- San Borja: dos reportes que terminan en un solo incidente confirmado y resuelto.
- Lince: dos reportes que terminan en un solo incidente confirmado y asignado.
- C1 (San Isidro): tres reportes del mismo sector, tipo y ventana; el seeder los
  deja pendientes de confirmar.
- C2 (Barranco): mismo sector y ventana, pero distinto tipo de falla; el seeder
  lo describe como Baja Certeza.
- C3 (Miraflores): mismo sector y tipo, fuera de la ventana; son casos distintos.
- C4 (Surco y Surquillo): sectores distintos con el mismo tipo y hora; casos
  distintos.
- C5: un reporte sin sector; Baja Certeza.

## 3. Metodología

1. Se cargaron los 15 reportes desde `scripts/datos/semillas_backend.csv`.
2. Se normalizó el sector igual que `TextNormalizer.normalizeKey` del backend:
   sin tildes, mayúsculas, sin signos y con espacios colapsados. Así
   `san isidro` y `San Isidro` caen en la misma clave.
3. Se formaron solo pares que comparten **sector normalizado y tipo de falla**,
   como pide el filtro del motor. No se aplicó la ventana temporal en el script;
   por eso el par R11/R12 aparece y se reporta aparte.
4. La similitud se calculó con `servicio.similitud`, la misma función del
   microservicio, importada directamente (sin HTTP).
5. Cada par se clasificó con los umbrales actuales:
   - `>= 0.55`: zona alta,
   - `0.30 – 0.55`: baja certeza (sin incluir 0.55),
   - `< 0.30`: zona baja.
6. Para las métricas etiquetadas se usó el corte binario `>= 0.55` como
   "mismo incidente" y `< 0.55` como "no mismo incidente". Las etiquetas son las del
   apartado 2.

Reproducción:

```powershell
.\.venv\Scripts\python.exe scripts\probar_con_semillas.py
```

También acepta otro CSV:

```powershell
.\.venv\Scripts\python.exe scripts\probar_con_semillas.py --entrada ruta\al.csv
```

## 4. Resultados

### 4.1 Reportes y pares

- Reportes: **15**
- Pares con mismo sector y tipo: **6**

| Zona | Pares |
| --- | ---: |
| `>= 0.55` (alta) | 1 |
| `0.30 – 0.55` (baja certeza) | 1 |
| `< 0.30` (baja) | 4 |

### 4.2 Métricas etiquetadas

El par R11/R12 es distinto incidente **solo por la ventana de tiempo**. El motor
real ni siquiera lo compara al construir candidatos, porque R11 está 110 minutos
antes que R12 y la ventana es de 30 minutos. Por eso se excluye de la métrica
principal; contarlo como acierto semántico inflaría el resultado.

**Métrica principal (5 pares, sin R11/R12):**

| Concepto | Valor |
| --- | ---: |
| Pares | 5 |
| Etiqueta "mismo incidente" | 5 |
| TP (`>= 0.55`) | 1 |
| FN (`< 0.55`) | 4 |
| FP | 0 |
| TN | no aplica: no hay negativos |

Con esta muestra no tiene sentido reportar precisión: no hay negativos. La
exhaustividad es 1/5 = 0.20. El único acierto positivo es R07/R08 (0.5556), que
apenas supera el umbral.

**Par R11/R12, separado:**

| Par | Similitud | Etiqueta | Resultado con 0.55 |
| --- | ---: | --- | --- |
| R11/R12 | 0.2591 | distinto incidente | TN |

Este par no es evidencia del modelo: la regla temporal ya lo descarta antes de
mirar la similitud. Se reporta solo porque el script, como se pidió, filtra por
sector y tipo sin ventana.

Si se sumaran los 6 pares, el conteo sería: 2 aciertos (1 TP + 1 TN), 0 FP y 4
FN. Es una suma engañosa porque mezcla dos escenarios distintos; por eso no se
usa como métrica principal.

### 4.3 Todos los pares

| Par | Sector / tipo | Similitud | Zona | Etiqueta | Predicción `>= 0.55` |
| --- | --- | ---: | --- | --- | --- |
| R01 / R02 | San Borja / BAJA_TENSION | 0.1150 | baja | mismo incidente | no |
| R04 / R05 | Lince / CORTE_TOTAL | 0.1953 | baja | mismo incidente | no |
| R06 / R07 | San Isidro / CORTE_TOTAL | 0.1604 | baja | mismo incidente | no |
| R06 / R08 | San Isidro / CORTE_TOTAL | 0.4942 | baja certeza | mismo incidente | no |
| R07 / R08 | San Isidro / CORTE_TOTAL | 0.5556 | alta | mismo incidente | sí |
| R11 / R12 | Miraflores / INTERMITENCIA | 0.2591 | baja | distinto incidente | no |

### 4.4 Pares mal clasificados (todos, con las dos descripciones)

Cuatro pares que deberían ser "mismo incidente" quedan por debajo de 0.55.

**R01 / R02 — similitud 0.1150 (falso negativo)**

- A: "Los focos estan muy bajos y la refrigeradora se apaga sola"
- B: "Baja tension en toda la cuadra, los equipos no encienden"

Posible explicación: ambos describen baja tensión, pero con vocabulario casi
disjunto ("focos bajos", "refrigeradora" frente a "baja tensión", "equipos").
Son frases cortas y el modelo no infiere la relación causa-efecto entre un
síntoma doméstico y la etiqueta técnica. No está verificado: es una hipótesis.

**R04 / R05 — similitud 0.1953 (falso negativo)**

- A: "Se fue la luz en toda la manzana despues de un chispazo"
- B: "Corte de energia en el edificio y en los vecinos"

Posible explicación: comparten la idea de corte, pero "manzana", "chispazo" y
"edificio" empujan la representación hacia contextos distintos. La frase A
incluye una causa (chispazo) que B no menciona.

**R06 / R07 — similitud 0.1604 (falso negativo)**

- A: "No hay luz en toda la cuadra desde hace 20 minutos"
- B: "Corte de energia en mi casa y en la de los vecinos"

Posible explicación: A describe una falla de cuadra y B una falla que empieza en
"mi casa"; el modelo separa ambos alcances. La etiqueta de "mismo incidente"
proviene de C1 en el seeder, no de una verdad de campo, así que este par es
especialmente discutible.

**R06 / R08 — similitud 0.4942 (falso negativo, cerca del umbral)**

- A: "No hay luz en toda la cuadra desde hace 20 minutos"
- B: "Se fue la electricidad en la zona"

Posible explicación: "luz" frente a "electricidad" y "cuadra" frente a "zona"
son sinónimos parciales. El valor queda a 0.0558 del umbral: un cambio pequeño
lo cruzaría. Esto muestra que el umbral 0.55 es frágil con estas descripciones.

El único positivo acertado es **R07 / R08 = 0.5556**, apenas 0.0056 por encima
del umbral. No es un margen cómodo.

## 5. Qué hace exactamente el motor con cada zona

Leído en `GroupingEngine` y `GroupingService` (solo lectura). El motor **no
descarta reportes por similitud**: si hay un incidente candidato, lo vincula y
solo cambia la certeza y la necesidad de revisión.

| Situación | Decisión | Certeza | `requiresReview` | Qué ve el operador |
| --- | --- | --- | --- | --- |
| Similitud `>= 0.55` | `VINCULAR` | ALTA | no | Caso vinculado con señal semántica suficiente. |
| Similitud `0.30 – 0.55` | `VINCULAR` | MEDIA | no | Caso vinculado; el motivo dice "confirmar manualmente". El mensaje al cliente dice "en revisión", pero el flag de revisión del incidente solo se activa con BAJA. |
| Similitud `<= 0.30` | `VINCULAR` | BAJA | sí | Caso marcado para revisión y "posible falso positivo"; no se descarta. |
| Tipo de falla distinto | `VINCULAR` | BAJA | sí | Vinculación tentativa al candidato del sector, con revisión. No usa similitud. |
| Sin candidatos en el sector | `NUEVA_INCIDENCIA` | ALTA | no | Caso nuevo. |
| Sin sector y sin candidatos | `NUEVA_INCIDENCIA` | BAJA | sí | Caso nuevo marcado para revisión. |
| Sin sector con candidato | `VINCULAR` | BAJA | sí | Vinculación tentativa por tipo y ventana, con revisión. |

Detalles que importan para la demo:

- `GroupingService` busca candidatos por sector, estado abierto y ventana de 30
  minutos. La consulta por sector **no** filtra por tipo; el motor elige primero
  un candidato del mismo tipo y, si no hay, usa el primero. Por eso C2 (Barranco,
  distinto tipo) se vincula con Baja Certeza.
- Para la similitud usa `maxSimilarity`: compara la descripción nueva con hasta
  4 descripciones recientes del incidente y toma el **máximo**, no el promedio.
  Por eso R08 puede quedar en ALTA con R07 (0.5556) aunque R06/R08 sea 0.4942.
- La certeza del incidente se recalcula como `worstOf` de las certezas de sus
  reportes. Un solo reporte BAJA deja todo el incidente en BAJA y
  `requiresReview=true` mientras siga abierto.
- `requiresReview` se apaga cuando el incidente deja de estar abierto (por
  ejemplo, RESUELTA), aunque la certeza siga en BAJA.

### 5.1 Qué vería el operador con estos 15 reportes

Esto se deduce del código y del orden del seeder; **no se ejecutó el backend**.

| Caso | Reportes | Resultado esperado |
| --- | ---: | --- |
| San Borja | 2 | Vinculado con BAJA por R02; el seeder lo confirma y lo resuelve, así que al final queda RESUELTA sin revisión pendiente. |
| Chorrillos | 1 | Incidente nuevo ALTA, luego EN_ATENCION. |
| Lince | 2 | Vinculado con BAJA por R05; el seeder lo confirma, pero al seguir CONFIRMADA y abierto queda con `requiresReview=true`. |
| San Isidro (C1) | 3 | R06 crea ALTA, R07 vincula BAJA y R08 vincula ALTA usando el máximo 0.5556. El incidente queda BAJA por `worstOf` y sigue SUGERIDA con revisión: es el caso C1. |
| Barranco (C2) | 2 | Tipo distinto: vincula BAJA con revisión. |
| Miraflores (C3) | 2 | R12 queda fuera de la ventana: dos incidentes ALTA separados. |
| Surco / Surquillo (C4) | 2 | Sectores distintos: dos incidentes ALTA separados. |
| Sin sector (C5) | 1 | Incidente nuevo BAJA con revisión. |

En resumen: el operador vería C1, C2 y C5 marcados para revisión, además de
Lince (confirmado pero con certeza BAJA). El resto aparece en ALTA. La similitud
baja no hace que un reporte se pierda: lo hace llegar con una advertencia.

## 6. Casos sugeridos (redactados por el asistente)

> **No son datos del backend.** Son 12 reportes redactados por el asistente para
> proponer a P3, en `scripts/datos/casos_sugeridos_backend.csv`. No se agregaron
> al backend y no se mezclan con las métricas de la sección 4.

El archivo forma 9 pares con mismo sector y tipo:

| Par | Sector / tipo | Similitud | Zona | Intención sugerida |
| --- | --- | ---: | --- | --- |
| S01 / S02 | La Molina / BAJA_TENSION | 0.2275 | baja | mismo incidente |
| S03 / S04 | Surco / CORTE_TOTAL | 0.3910 | baja certeza | mismo incidente |
| S03 / S05 | Surco / CORTE_TOTAL | 0.6169 | alta | distinto (falla interna) |
| S04 / S05 | Surco / CORTE_TOTAL | 0.3286 | baja certeza | distinto (falla interna) |
| S06 / S07 | La Victoria / INTERMITENCIA | 0.3457 | baja certeza | mismo incidente |
| S08 / S09 | Miraflores / ALUMBRADO_PUBLICO | 0.3752 | baja certeza | mismo incidente |
| S08 / S10 | Miraflores / ALUMBRADO_PUBLICO | 0.5600 | alta | distinto (una luminaria) |
| S09 / S10 | Miraflores / ALUMBRADO_PUBLICO | 0.4085 | baja certeza | distinto (una luminaria) |
| S11 / S12 | San Miguel / MEDIDOR | 0.5584 | alta | mismo incidente |

Si se aplicaran las etiquetas sugeridas, el ejercicio daría 3 aciertos, 2 falsos
positivos y 4 falsos negativos. Es solo un ejercicio con etiquetas del propio
asistente, no un resultado del backend; por eso queda fuera de la tabla
principal. Los pares exportados están en
`docs/prueba_semillas_sugeridos_pares.csv`.

Sirven para ampliar la demo con negativos difíciles (misma zona y tipo, distinto
alcance) y con paráfrasis que el modelo actual puntúa bajo.

## 7. Limitaciones

- Las etiquetas salen de comentarios del mismo equipo que escribió las
  descripciones. **No es una validación independiente.**
- Solo 15 reportes y 6 pares; 5 son "mismo incidente" y 1 es negativo. La muestra
  es demasiado pequeña para estimar desempeño.
- El filtro de pares (sector + tipo) deja fuera C2 (distinto tipo), C4 (distintos
  sectores) y C5 (sin sector). No se evalúan esos caminos del motor.
- El script no aplica la ventana temporal; por eso R11/R12 aparece y se separa.
- Las descripciones son frases cortas escritas en código, sin tildes y con estilo
  homogéneo. No representan reportes reales de clientes.
- La similitud es solo una señal: el motor vincula igual y marca certeza. Un
  "falso negativo" con 0.55 no significa que el reporte se descarte; significa
  que no recibe la certeza ALTA.
- No se ejecutó el backend ni el seeder; el comportamiento de la sección 5 se
  dedujo leyendo el código.
- No se usó esta muestra para calibrar y no se cambiaron los umbrales 0.55/0.30.

## 8. Conclusión

En esta prueba de humo, el modelo acertó solo **1 de 5** pares que deberían ser
el mismo incidente (R07/R08, 0.5556) y dejó los otros cuatro por debajo de 0.55.
Tres de esos cuatro quedaron incluso por debajo de 0.30.

Esto **no demuestra** que el modelo sea malo en producción: la muestra es
mínima, las etiquetas son del mismo equipo y el motor real sigue vinculando y
marcando revisión en lugar de descartar. Pero sí muestra que estas descripciones
demo no son un caso fácil y que el margen del umbral 0.55 es estrecho.

No se recomienda mover umbrales con estos datos. La prueba debe repetirse con
más casos y, idealmente, con descripciones reales anonimizadas y validadas por
operadores. Los 12 reportes sugeridos del apartado 6 son un siguiente paso
razonable para ampliar la demo, no una validación.

## 9. Archivos

- `scripts/probar_con_semillas.py`: cálculo y reporte.
- `scripts/datos/semillas_backend.csv`: 15 reportes demo con etiquetas derivadas.
- `scripts/datos/casos_sugeridos_backend.csv`: 12 reportes sugeridos por el asistente.
- `docs/prueba_semillas_pares.csv`: los 6 pares del demo.
- `docs/prueba_semillas_sugeridos_pares.csv`: los 9 pares sugeridos, separados.
