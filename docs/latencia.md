# Latencia del microservicio de similitud

- Fecha: 2026-11-16T16:15:14-05:00
- Máquina: STG_PERU (Windows 11)
- CPU: Intel64 Family 6 Model 140 Stepping 1, GenuineIntel (8 núcleos lógicos)
- RAM: 7.7 GB
- Python: 3.12.10
- torch: 2.15.0+cpu
- Modelo: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
- Servidor: http://127.0.0.1:8000
- Repeticiones por escenario: 30
- Timeout del backend: 1500 ms

| Escenario | p50 (ms) | p95 (ms) | máx (ms) | media (ms) | margen p95 (ms) |
| --- | ---: | ---: | ---: | ---: | ---: |
| /api/v1/similarity | 56.3 | 66.7 | 76.1 | 57.3 | 1433.3 |
| batch 10 | 135.2 | 147.0 | 151.9 | 135.8 | 1353.0 |
| batch 50 | 548.0 | 603.6 | 723.1 | 558.0 | 896.4 |
| batch 200 | 2032.2 | 2074.2 | 2118.8 | 2029.3 | -574.2 |

No hay margen: algun p95 supera el timeout de 1,5 s del backend.

## Contexto

El backend de incidencias envía como máximo 4 descripciones por lote (solo las
del mejor incidente). El escenario de 200 candidatos representa el límite del
contrato, no el uso real; con 4 candidatos se espera una latencia menor que la
del lote de 10 medido, que sí tiene margen.
