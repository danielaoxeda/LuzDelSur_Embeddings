# AGENTS.md

Microservicio de similitud semantica para las descripciones de fallas de Luz del Sur.
La IA solo sugiere; el operador humano decide.

## Reglas

- Codigo, variables y comentarios en espanol; terminos tecnicos en ingles.
- Comentarios de una linea, cortos y claros.
- No instalar dependencias globales: usar `.venv`.
- No hacer `git push` sin autorizacion explicita.
- Commits en espanol, imperativos y breves.
- No inventar datos ni resultados.

## Contrato

- `GET /health` -> `{"estado": "ok", "modelo": "...", "modelo_cargado": true}`
- `POST /api/v1/similarity` -> `{"text_a": "...", "text_b": "..."}` -> `{"similarity": 0.0}`
- `POST /api/v1/similarity/batch` -> `{"text": "...", "candidates": ["..."]}` -> `{"similarities": [0.0]}`
- Similitud coseno acotada a 0-1 y redondeada a 4 decimales.
- Textos vacios devuelven 0.0, igual que el contrato del backend.
- Maximo 200 candidatos y 1000 caracteres por texto.
- El modelo se carga una sola vez en el `lifespan`.

## Comandos

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000
```
