# LuzDelSur_Embeddings

Microservicio en FastAPI que calcula la similitud semantica entre descripciones
de fallas electricas. Es una senal auxiliar: el backend y el operador humano
conservan la decision final.

- Modelo por defecto: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- Un solo proceso de uvicorn: el modelo se carga una vez.
- El servicio no decide agrupaciones; solo devuelve similitudes.

Documentacion adicional: `docs/integracion-docker.md` (compose del backend),
`docs/latencia.md` (mediciones) y `docs/calibracion.md` (pares sinteticos).

## Contrato

### `GET /health`

```bash
curl http://127.0.0.1:8000/health
```

```json
{"estado":"ok","modelo":"sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2","modelo_cargado":true}
```

Si el modelo no carga, `estado` es `degradado` y `modelo_cargado` es `false`.

### `POST /api/v1/similarity`

```bash
curl -X POST http://127.0.0.1:8000/api/v1/similarity \
  -H "Content-Type: application/json" \
  -d '{"text_a":"Se escuchó una explosión y se apagó toda mi cuadra","text_b":"Sonó un fuerte ruido del transformador y no hay luz"}'
```

```json
{"similarity":0.6076}
```

El valor mostrado corresponde a una medicion real de esos dos textos.

### `POST /api/v1/similarity/batch`

```bash
curl -X POST http://127.0.0.1:8000/api/v1/similarity/batch \
  -H "Content-Type: application/json" \
  -d '{"text":"Se escuchó una explosión y se apagó toda mi cuadra","candidates":["Sonó un fuerte ruido del transformador y no hay luz","Mi luz parpadea solo en mi casa"]}'
```

```json
{"similarities":[0.6076,0.4255]}
```

El orden de `similarities` coincide con el orden de `candidates`.

## Requisitos

- Python 3.12
- Entorno virtual `.venv` (no instalar dependencias globales)

## Instalacion y ejecucion local

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

En Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

El modelo se carga una sola vez al iniciar. La primera ejecucion descarga
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` a la cache local;
la imagen Docker ya lo trae descargado.

## Docker

```bash
docker build -t luzdelsur/embeddings:local .
docker run --rm -p 127.0.0.1:8000:8000 luzdelsur/embeddings:local
```

O con el compose de ejemplo de este repositorio:

```bash
docker compose up --build
```

La imagen:

- usa `python:3.12-slim` y ejecuta como usuario sin privilegios (`app`);
- instala `torch` CPU desde `https://download.pytorch.org/whl/cpu`;
- descarga el modelo durante el build, no al arrancar;
- corre un solo worker de uvicorn en el puerto 8000;
- tiene `HEALTHCHECK` contra `/health` que exige `modelo_cargado: true`.

El compose de ejemplo incluye un limite de memoria de 1.5 GB como **valor de
partida no validado** (`EMBEDDINGS_MEM_LIMIT`, por defecto `1536m`). Hay que
medirlo en el servidor con `docker stats` antes de produccion.

### Medicion en el servidor

Como esta maquina de desarrollo no tiene Docker, el build, el tamano, la
memoria y la latencia del contenedor estan **PENDIENTES DE MEDIR EN EL SERVIDOR**.
En un Linux con Docker:

```bash
bash scripts/medir_docker.sh
```

El script mide build, arranque, respuestas, `docker stats`, lote de 4 y la
latencia con `scripts/medir_latencia.py`. Guarda todo en
`docs/medicion_docker_<fecha>.txt` y falla con un mensaje claro si Docker no
responde o si el puerto 8000 esta ocupado.

### Integracion con el backend

El backend lee `app.embeddings.base-url` desde `EMBEDDINGS_BASE_URL`, por
defecto `http://localhost:8000`. Dentro del compose debe apuntar a
`http://embeddings:8000`, con el servicio llamado `embeddings` en la misma red.
El fragmento listo para copiar y el orden de arranque estan en
`docs/integracion-docker.md`. No se modifico el backend.

## Variables de entorno

Ver `.env.example`. Todas son opcionales.

| Variable | Por defecto | Uso |
| --- | --- | --- |
| `EMBEDDINGS_MODEL` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Modelo de embeddings |
| `EMBEDDINGS_DEVICE` | `cpu` | Dispositivo de ejecucion |
| `EMBEDDINGS_MAX_CANDIDATOS` | `200` | Maximo de candidatos por lote |
| `EMBEDDINGS_MAX_CARACTERES` | `1000` | Maximo de caracteres por texto |
| `LOG_LEVEL` | `INFO` | Nivel de log (INFO, DEBUG, WARNING, ERROR) |

En Docker, `EMBEDDINGS_MODEL` tambien se pasa como argumento de build
(`MODELO_EMBEDDINGS`) para hornear ese modelo en la imagen. Si se cambia solo en
tiempo de ejecucion por un modelo no incluido, se descargara al arrancar.

## Limites y errores

- Cada texto admite hasta 1000 caracteres.
- Un lote admite hasta 200 candidatos.
- Si se supera un limite o falta un campo, la respuesta es `422` con un mensaje
  claro en espanol.
- Si el modelo no esta cargado o falla, `/health` informa
  `"modelo_cargado": false` y los endpoints responden `503` con JSON.
- Un lote vacio devuelve `{"similarities": []}`. Un candidato vacio devuelve
  `0.0` en su posicion.

## Registro de peticiones

Cada peticion registra solo metodo, ruta, codigo, duracion en milisegundos y
cantidad de candidatos. Nunca se registra el contenido de los textos. El nivel
se configura con `LOG_LEVEL`.

## Latencia

Medicion local (Windows 11, CPU, 30 repeticiones por escenario):

| Escenario | p50 (ms) | p95 (ms) | max (ms) |
| --- | ---: | ---: | ---: |
| `/api/v1/similarity` | 56.3 | 66.7 | 76.1 |
| batch 10 | 135.2 | 147.0 | 151.9 |
| batch 50 | 548.0 | 603.6 | 723.1 |
| batch 200 | 2032.2 | 2074.2 | 2118.8 |

El backend usa un timeout de 1500 ms. El lote de 200 candidatos no tiene margen
en esta medicion; el uso real del backend envia pocas descripciones (hasta 5
segun `GROUPING_MAX_CANDIDATES`, y en la practica las del mejor incidente), por
lo que queda margen. La comparacion con Docker esta pendiente de medir en el
servidor.

Para repetir la medicion local:

```powershell
.\.venv\Scripts\python scripts/medir_latencia.py
```

El script calienta el modelo y mide `/similarity`, lote de 10, 50 y 200. Guarda
el resultado en `docs/latencia.md`. Requiere `requirements-dev.txt` (usa `httpx`).

## Pruebas

Las pruebas y la medicion de latencia usan dependencias de desarrollo, que no
entran en la imagen Docker:

```powershell
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest
```

Actualmente son 11 pruebas del contrato, validacion y errores del modelo.

## Calibracion

`docs/calibracion.md` documenta un estudio con 60 pares sinteticos. Los datos y
las etiquetas fueron redactados por el equipo, no provienen de reportes reales
de Luz del Sur. La conclusion de ese estudio es no cambiar los umbrales
0.55/0.30 del backend con esa muestra.
