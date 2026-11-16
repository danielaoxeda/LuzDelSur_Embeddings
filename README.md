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

## Pruebas

```powershell
.\.venv\Scripts\python -m pytest
```

## Variables de entorno

Ver `.env.example`. Las variables son opcionales y tienen valores por defecto.
