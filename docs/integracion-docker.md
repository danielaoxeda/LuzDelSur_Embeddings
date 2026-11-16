# Integración del microservicio de embeddings en Docker

Este documento es para quien mantiene el compose del backend. **No se modificó
ningún archivo del backend**; el fragmento de abajo se copia en su repositorio.

## 1. Cómo configura el backend la URL (solo lectura)

En `backend/src/main/resources/application.yml`:

```yaml
app:
  embeddings:
    enabled: ${EMBEDDINGS_ENABLED:true}
    base-url: ${EMBEDDINGS_BASE_URL:http://localhost:8000}
    timeout-ms: ${EMBEDDINGS_TIMEOUT_MS:1500}
    cooldown-seconds: ${EMBEDDINGS_COOLDOWN_SECONDS:30}
    match-threshold: ${EMBEDDINGS_MATCH_THRESHOLD:0.55}
    conflict-threshold: ${EMBEDDINGS_CONFLICT_THRESHOLD:0.30}
```

- Propiedad Spring: `app.embeddings.base-url`.
- Variable de entorno: **`EMBEDDINGS_BASE_URL`**.
- Valor por defecto: `http://localhost:8000`.
- No hay propiedades separadas de host y puerto: ambos van dentro de
  `EMBEDDINGS_BASE_URL`.
- El microservicio escucha en `0.0.0.0:8000` dentro del contenedor.
- Timeout del cliente: `EMBEDDINGS_TIMEOUT_MS`, por defecto **1500 ms**.

## 2. Nombres para el compose del backend

| Dato | Valor |
| --- | --- |
| Nombre del servicio | `embeddings` |
| Host interno (DNS de la red) | `embeddings` |
| Puerto interno | `8000` |
| URL que debe usar el backend | `http://embeddings:8000` |
| Variable del backend | `EMBEDDINGS_BASE_URL=http://embeddings:8000` |

El backend y este servicio deben estar en la **misma red de Docker**. El nombre
`embeddings` resuelve por DNS dentro de esa red; no hace falta publicar el
puerto 8000 al exterior.

## 3. Fragmento listo para copiar al compose del backend

Ajustar el nombre de la red (`internal`) si su compose usa otro.

```yaml
services:
  embeddings:
    image: luzdelsur/embeddings:latest
    container_name: lds-embeddings
    environment:
      EMBEDDINGS_MODEL: ${EMBEDDINGS_MODEL:-sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    expose:
      - "8000"
    # 1536m = 1.5 GB. Valor de partida NO validado: medir con docker stats.
    mem_limit: ${EMBEDDINGS_MEM_LIMIT:-1536m}
    restart: unless-stopped
    networks:
      - internal
    healthcheck:
      test: ["CMD", "python", "-c", 'import json, sys, urllib.request; datos = json.load(urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=4)); sys.exit(0 if datos.get("modelo_cargado") is True else 1)']
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 90s

  backend:
    environment:
      EMBEDDINGS_ENABLED: ${EMBEDDINGS_ENABLED:-true}
      EMBEDDINGS_BASE_URL: http://embeddings:8000
      EMBEDDINGS_TIMEOUT_MS: ${EMBEDDINGS_TIMEOUT_MS:-1500}
      EMBEDDINGS_COOLDOWN_SECONDS: ${EMBEDDINGS_COOLDOWN_SECONDS:-30}
      EMBEDDINGS_MATCH_THRESHOLD: ${EMBEDDINGS_MATCH_THRESHOLD:-0.55}
      EMBEDDINGS_CONFLICT_THRESHOLD: ${EMBEDDINGS_CONFLICT_THRESHOLD:-0.30}
    depends_on:
      db:
        condition: service_healthy
      embeddings:
        condition: service_healthy
```

> El compose actual del backend ya define un servicio `embeddings` con
> `EMBEDDINGS_BASE_URL: http://embeddings:8000`, pero usa
> `depends_on: condition: service_started`. La condición recomendada es
> **`service_healthy`**, para que el backend no arranque hasta que el modelo
> esté cargado. Esa decisión corresponde al equipo del backend.

## 4. Orden de arranque

1. `db` (PostgreSQL) queda `healthy`.
2. `embeddings` queda `healthy` cuando `/health` responde
   `"modelo_cargado": true`.
3. `backend` arranca después y usa `http://embeddings:8000`.

El modelo viene horneado en la imagen, así que el arranque no depende de
descargarlo desde Hugging Face. Si se cambia `EMBEDDINGS_MODEL` en tiempo de
ejecución por un modelo que no está en la imagen, ese modelo sí se descargaría
al arrancar y el `start_period` podría no alcanzar.

## 5. Verificación desde el contenedor del backend

```bash
docker compose exec backend wget -qO- http://embeddings:8000/health
```

Debe devolver `200` con `"modelo_cargado": true`. Si el modelo falla, el
microservicio responde `503` en los endpoints y el backend sigue operando con
sus reglas heurísticas, tal como ya está diseñado.

## 6. Medición pendiente

El límite de 1.5 GB y la latencia en Docker **no se midieron en esta máquina**
porque no hay Docker instalado. En el servidor, ejecutar desde este repositorio:

```bash
bash scripts/medir_docker.sh
```

El script guarda tamaño, tiempos, memoria, respuestas y latencia en
`docs/medicion_docker_<fecha>.txt`. Hasta entonces, el límite de memoria es solo
un valor de partida y no una cifra validada.
