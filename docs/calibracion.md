# Calibración de umbrales de similitud

> **Aviso sobre los datos.** Los 60 pares de `scripts/datos/pares_calibracion.csv`
> y sus etiquetas fueron redactados por el equipo para este ejercicio. Son datos
> **sintéticos** y **no provienen de reportes reales de Luz del Sur**. Varias
> descripciones se inspiraron en ejemplos públicos de la documentación y las
> pruebas del backend (solo lectura), pero las etiquetas son una decisión del
> equipo y no una verdad de campo.

## 1. Objetivo

Evaluar con datos simulados qué tan bien separa el modelo actual
(`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`) los pares de
descripciones que describen la misma falla de los que describen fallas
distintas, proponer umbrales y comparar contra una línea base TF-IDF.

## 2. Datos encontrados en el backend (solo lectura)

No hay semillas de reportes en Flyway: `V1__baseline.sql` y
`V2__technician_assignment.sql` solo definen el esquema. Las descripciones
aparecen en documentación y pruebas:

| Ruta | Ejemplos |
| --- | --- |
| `docs/api.md` | "No hay luz en toda la cuadra desde hace 20 minutos", "Sigue sin luz en la cuadra", "No hay luz en la cuadra", "Corte de energia en la zona", "Falla del medidor" |
| `backend/src/test/.../ReportFlowIntegrationTest.java` | "Corte total de luz en toda la cuadra", "No hay energia electrica en mi vivienda", "Corte total en la cuadra", "Seguimos sin energia" |
| `backend/src/test/.../GroupingEngineTest.java` | "No hay luz en toda la cuadra", "Corte de luz general" |
| `docs/integracion-equipo.md` | Recomienda variantes como "no hay luz", "corte de energía", "se fue la electricidad", "el medidor hace ruido" |

Se usaron varias de esas frases dentro de los pares. No se modificó ningún
archivo del backend.

## 3. Conjunto etiquetado

- Archivo: `scripts/datos/pares_calibracion.csv`.
- 60 pares: 30 con `misma_falla=1` y 30 con `misma_falla=0`.
- Textos de 20 a 50 caracteres, con sinónimos, errores ortográficos, ausencia de
  tildes, mayúsculas, vocabulario coloquial peruano y frases cortas.
- Escenarios: corte total de la cuadra, ruido o explosión en transformador,
  cable caído o chispas, baja tensión o parpadeo de zona, falla interna de una
  vivienda, poste dañado y fuga o cortocircuito.
- Negativos difíciles con el mismo vocabulario (por ejemplo "no hay luz en mi
  casa" por falla interna frente a "corte total en la cuadra") y positivos
  escritos con palabras muy distintas.
- La etiqueta es del equipo; no hay verificación externa.

### División calibración / evaluación

Semilla fija `20261116`, estratificada por clase: 15 positivos y 15 negativos en
cada partición. La asignación se guarda en
`scripts/datos/particiones_calibracion.csv`.

- Calibración: `P02 P03 P04 P05 P06 P08 P09 P10 P14 P15 P16 P18 P22 P23 P27`
  y `N02 N03 N05 N09 N10 N11 N12 N14 N17 N18 N22 N23 N25 N27 N28`.
- Evaluación: `P01 P07 P11 P12 P13 P17 P19 P20 P21 P24 P25 P26 P28 P29 P30`
  y `N01 N04 N06 N07 N08 N13 N15 N16 N19 N20 N21 N24 N26 N29 N30`.

## 4. Metodología

1. Se calculó la similitud de cada par con `servicio.similitud`, la misma
   función del microservicio, importada directamente (sin HTTP).
2. Con **calibración** se barrió el umbral de 0.20 a 0.90 en pasos de 0.05 y se
   calculó precisión, exhaustividad y F1.
3. Reglas propuestas:
   - `umbral_alto`: el más bajo con precisión ≥ 0.90 en calibración.
   - `umbral_bajo`: el más alto con exhaustividad ≥ 0.95 en calibración.
   - La zona `[umbral_bajo, umbral_alto)` se denomina **Baja Certeza**.
4. Con **evaluación** se aplicaron los umbrales propuestos y los actuales del
   backend (0.55 y 0.30), y se obtuvo la matriz de confusión.
5. Línea base TF-IDF: `TfidfVectorizer(ngram_range=(1,2), strip_accents=None,
   stop_words=None)` ajustado sobre los 120 textos de los 60 pares (vocabulario
   no supervisado, sin usar etiquetas) y similitud coseno por par.
6. La AUC se calculó con `roc_auc_score` sobre las similitudes continuas.

Reproducción:

```powershell
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python scripts\calibrar.py
```

## 5. Calibración: barrido de umbrales

### 5.1 Embeddings

| Umbral | Precisión | Exhaustividad | F1 |
| ---: | ---: | ---: | ---: |
| 0.20 | 0.48 | 0.93 | 0.64 |
| 0.25 | 0.48 | 0.93 | 0.64 |
| 0.30 | 0.48 | 0.87 | 0.62 |
| 0.35 | 0.48 | 0.87 | 0.62 |
| 0.40 | 0.52 | 0.87 | 0.65 |
| 0.45 | 0.57 | 0.87 | 0.68 |
| 0.50 | 0.56 | 0.67 | 0.61 |
| 0.55 | 0.59 | 0.67 | 0.63 |
| 0.60 | 0.63 | 0.67 | 0.65 |
| 0.65 | 0.67 | 0.53 | 0.59 |
| 0.70 | 0.80 | 0.53 | 0.64 |
| 0.75 | 0.75 | 0.40 | 0.52 |
| 0.80 | 0.67 | 0.13 | 0.22 |
| 0.85 | 1.00 | 0.07 | 0.13 |
| 0.90 | 1.00 | 0.07 | 0.13 |

**Propuesta con las reglas:** `umbral_alto = 0.85` (precisión 1.00,
exhaustividad 0.07) y `umbral_bajo = 0.20`, este último por respaldo: ningún
umbral alcanza exhaustividad ≥ 0.95; el máximo es 0.93 en 0.20. Es decir, la
regla se cumple, pero produce un umbral alto prácticamente inutilizable y un
umbral bajo sin capacidad de descarte.

### 5.2 TF-IDF

| Umbral | Precisión | Exhaustividad | F1 |
| ---: | ---: | ---: | ---: |
| 0.20 | 0.64 | 0.60 | 0.62 |
| 0.25 | 0.62 | 0.53 | 0.57 |
| 0.30 | 0.56 | 0.33 | 0.42 |
| 0.35 | 0.40 | 0.13 | 0.20 |
| 0.40 | 0.40 | 0.13 | 0.20 |
| 0.45 | 0.50 | 0.13 | 0.21 |
| 0.50 | 0.50 | 0.13 | 0.21 |
| 0.55 | 0.67 | 0.13 | 0.22 |
| 0.60 | 1.00 | 0.13 | 0.24 |
| 0.65 | 1.00 | 0.13 | 0.24 |
| 0.70 | 1.00 | 0.07 | 0.13 |
| 0.75 | 0.00 | 0.00 | 0.00 |
| 0.80 | 0.00 | 0.00 | 0.00 |
| 0.85 | 0.00 | 0.00 | 0.00 |
| 0.90 | 0.00 | 0.00 | 0.00 |

**Propuesta con las reglas:** `umbral_alto = 0.60` (precisión 1.00,
exhaustividad 0.13) y `umbral_bajo = 0.20` por respaldo (exhaustividad 0.60,
tampoco alcanza 0.95).

## 6. Evaluación sobre la partición reservada

### 6.1 Métricas

| Modelo | Regla | Umbral | Precisión | Exhaustividad | F1 | TP | FP | TN | FN |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Embeddings | propuesto_alto | 0.85 | 0.86 | 0.40 | 0.55 | 6 | 1 | 14 | 9 |
| Embeddings | propuesto_bajo | 0.20 | 0.50 | 1.00 | 0.67 | 15 | 15 | 0 | 0 |
| Embeddings | actual | 0.55 | **0.71** | **0.80** | **0.75** | 12 | 5 | 10 | 3 |
| Embeddings | actual | 0.30 | 0.54 | 1.00 | 0.70 | 15 | 13 | 2 | 0 |
| TF-IDF | propuesto_alto | 0.60 | 0.00 | 0.00 | 0.00 | 0 | 1 | 14 | 15 |
| TF-IDF | propuesto_bajo | 0.20 | 0.64 | 0.60 | 0.62 | 9 | 5 | 10 | 6 |
| TF-IDF | actual | 0.55 | 0.00 | 0.00 | 0.00 | 0 | 2 | 13 | 15 |
| TF-IDF | actual | 0.30 | 0.58 | 0.47 | 0.52 | 7 | 5 | 10 | 8 |

Matriz de confusión del umbral propuesto alto (embeddings, 0.85):

|  | Predicho: misma falla | Predicho: distinta |
| --- | ---: | ---: |
| **Real: misma falla** | 6 | 9 |
| **Real: distinta** | 1 | 14 |

Matriz de confusión del umbral actual 0.55 (embeddings):

|  | Predicho: misma falla | Predicho: distinta |
| --- | ---: | ---: |
| **Real: misma falla** | 12 | 3 |
| **Real: distinta** | 5 | 10 |

Zona de **Baja Certeza** con los umbrales propuestos de embeddings
`[0.20, 0.85)`: contiene **23 de 30** pares de evaluación. Es demasiado ancha
para ser útil: casi todo quedaría para revisión humana.

### 6.2 Pares mal clasificados (embeddings)

Con el umbral propuesto alto 0.85:

| ID | Tipo | Similitud | Escenario | Par |
| --- | --- | ---: | --- | --- |
| N29 | falso positivo | 0.8563 | cable_tv_vs_electrico | se cayo la señal de cable / se cayo un cable de luz |
| P01 | falso negativo | 0.5861 | corte_cuadra | no hay luz en toda la cuadra / toda la cuadra esta sin energia |
| P07 | falso negativo | 0.5005 | transformador | se escucho una explosion en el transformador / sono un estruendo en el transformador |
| P11 | falso negativo | 0.6746 | transformador | el transformador hace un zumbido raro / zumba el transformador y huele a quemado |
| P12 | falso negativo | 0.8386 | cable_chispas | hay un cable caido en la pista / un cable esta en el suelo con chispas |
| P19 | falso negativo | 0.3255 | baja_tension_zona | baja tension en la cuadra / el voltaje baja en toda la calle |
| P20 | falso negativo | 0.6554 | falla_interna | no hay luz solo en mi casa / No hay energia electrica en mi vivienda |
| P24 | falso negativo | 0.4767 | poste_danado | un poste esta inclinado en la esquina / el poste de luz se ve chueco |
| P26 | falso negativo | 0.7886 | poste_danado | el poste esta dañado y suelta chispas / poste dañado con chispas en la calle |
| P29 | falso negativo | 0.6312 | fuga_cortocircuito | se produjo un cortocircuito en la casa / hubo un corto en la instalacion |

Con el umbral actual 0.55 (para comparar con la recomendación):

| ID | Tipo | Similitud | Escenario | Par |
| --- | --- | ---: | --- | --- |
| N04 | falso positivo | 0.7087 | transformador_vs_medidor | mi medidor hace ruido / ruido fuerte en el transformador |
| N15 | falso positivo | 0.7133 | medidor_vs_poste | el medidor esta dañado / el poste esta dañado |
| N20 | falso positivo | 0.7800 | interna_vs_transformador | se quemo el foco del pasillo / se quemo el transformador |
| N29 | falso positivo | 0.8563 | cable_tv_vs_electrico | se cayo la señal de cable / se cayo un cable de luz |
| N30 | falso positivo | 0.7535 | fuga_agua_vs_corriente | hay una fuga de agua en la pista / hay una fuga de corriente |
| P07 | falso negativo | 0.5005 | transformador | se escucho una explosion en el transformador / sono un estruendo en el transformador |
| P19 | falso negativo | 0.3255 | baja_tension_zona | baja tension en la cuadra / el voltaje baja en toda la calle |
| P24 | falso negativo | 0.4767 | poste_danado | un poste esta inclinado en la esquina / el poste de luz se ve chueco |

### 6.3 Pares mal clasificados (TF-IDF, umbral propuesto 0.60)

El umbral alto de TF-IDF no clasifica correctamente ningún positivo en
evaluación: los 15 positivos quedan por debajo de 0.60 y solo hay un falso
positivo.

| ID | Tipo | Similitud | Escenario |
| --- | --- | ---: | --- |
| N30 | falso positivo | 0.6053 | fuga_agua_vs_corriente |
| P01 | falso negativo | 0.3438 | corte_cuadra |
| P07 | falso negativo | 0.1893 | transformador |
| P11 | falso negativo | 0.1300 | transformador |
| P12 | falso negativo | 0.1907 | cable_chispas |
| P13 | falso negativo | 0.4267 | cable_chispas |
| P17 | falso negativo | 0.5241 | baja_tension_zona |
| P19 | falso negativo | 0.1477 | baja_tension_zona |
| P20 | falso negativo | 0.2697 | falla_interna |
| P21 | falso negativo | 0.3876 | falla_interna |
| P24 | falso negativo | 0.0496 | poste_danado |
| P25 | falso negativo | 0.4108 | poste_danado |
| P26 | falso negativo | 0.2091 | poste_danado |
| P28 | falso negativo | 0.3344 | fuga_cortocircuito |
| P29 | falso negativo | 0.1023 | fuga_cortocircuito |
| P30 | falso negativo | 0.3134 | fuga_cortocircuito |

## 7. Comparación embeddings vs TF-IDF

| Métrica | Embeddings | TF-IDF |
| --- | ---: | ---: |
| AUC calibración | 0.649 | 0.540 |
| AUC evaluación | **0.773** | 0.653 |
| Mejor F1 en evaluación | **0.75** (umbral 0.55) | 0.62 (umbral 0.20) |
| Precisión en ese punto | 0.71 | 0.64 |
| Exhaustividad en ese punto | 0.80 | 0.60 |
| Umbral propuesto alto | 0.85 | 0.60 |

Los embeddings separan mejor que TF-IDF en AUC y en mejor F1. Aun así, el
modelo no logra una separación limpia: hay un grupo de pares casi idénticos con
similitud alta (0.85-0.95) y otro de paráfrasis con similitud baja (0.30-0.60),
mientras varios negativos comparten vocabulario y suben a 0.70-0.86.

La figura `docs/calibracion_distribucion.png` muestra ese solapamiento y
`docs/calibracion_umbrales.png` muestra precisión y exhaustividad por umbral.

## 8. Limitaciones

- Solo 60 pares, escritos y etiquetados por el mismo equipo que evalúa: hay
  riesgo de sesgo y de sobreajuste a nuestras propias frases.
- Los negativos difíciles están sobrerrepresentados a propósito; no reflejan la
  proporción real de reportes.
- Una sola división calibración/evaluación: no hay validación cruzada y las
  métricas tienen alta varianza con 30 pares por partición.
- Los umbrales se eligieron con 30 pares, así que un solo par mueve la precisión
  varios puntos.
- TF-IDF se ajustó sobre los 120 textos de los 60 pares (sin etiquetas). Es una
  práctica habitual en corpus pequeños, pero el vocabulario incluye evaluación.
- No se usaron datos reales de Luz del Sur ni validación con operadores.
- Los resultados describen este conjunto sintético; **no deben extrapolarse** a
  reportes reales ni usarse como evidencia de producción.

## 9. Conclusión y recomendación

En este conjunto sintético, el modelo actual distingue bien los pares casi
idénticos, pero confunde paráfrasis con vocabulario distinto y negativos que
comparten palabras. Aplicar literalmente las reglas de calibración produce
umbrales poco útiles (`alto=0.85` con exhaustividad 0.40 en evaluación y
`bajo=0.20` sin descarte). El umbral actual **0.55** obtiene el mejor F1 de
evaluación (0.75) y **0.30** mantiene exhaustividad total a costa de muchos
falsos positivos.

**Recomendación:** no cambiar los umbrales 0.55/0.30 del backend con base en
esta muestra. Mantener 0.55 como umbral de vinculación automática y 0.30 como
límite inferior de Baja Certeza. Antes de moverlos, conviene repetir el estudio
con más pares y, idealmente, con descripciones reales anonimizadas y validadas
por operadores; recién entonces tendría sentido calibrar con validación cruzada
y reportar intervalos de confianza.

Esta recomendación es una propuesta del equipo de embeddings; la decisión final
del backend queda en sus responsables.

## 10. Archivos generados

- `scripts/datos/pares_calibracion.csv`: 60 pares etiquetados.
- `scripts/datos/particiones_calibracion.csv`: división reproducible.
- `scripts/calibrar.py`: cálculo completo con semilla fija.
- `docs/calibracion_resultados.csv`: barridos, métricas y AUC.
- `docs/calibracion_pares.csv`: similitud por par para auditar umbrales.
- `docs/calibracion_distribucion.png`: histograma por clase.
- `docs/calibracion_umbrales.png`: precisión y exhaustividad por umbral.
