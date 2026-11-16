# LuzDelSur_Embeddings

Microservicio en FastAPI que calcula la similitud semantica entre descripciones
de fallas electricas. Es una senal auxiliar: el backend y el operador humano
conservan la decision final.

## Requisitos

- Python 3.12
- Entorno virtual `.venv` (no instalar dependencias globales)

## Instalacion

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

## Ejecucion

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

El modelo se carga una sola vez al iniciar. La primera ejecucion descarga
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` a la cache local.

## Endpoints

- `GET /health`
- `POST /api/v1/similarity` con `{"text_a": "...", "text_b": "..."}`
- `POST /api/v1/similarity/batch` con `{"text": "...", "candidates": ["..."]}`

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

## Pruebas

```powershell
.\.venv\Scripts\python -m pytest
```

## Latencia

Con el servidor local en marcha:

```powershell
.\.venv\Scripts\python scripts/medir_latencia.py
```

El script calienta el modelo y mide `/similarity`, lote de 10, 50 y 200.
Guarda el resultado en `docs/latencia.md`.

## Variables de entorno

Ver `.env.example`. Las variables son opcionales y tienen valores por defecto.
