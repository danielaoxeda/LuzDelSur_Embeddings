# Imagen CPU del microservicio de similitud semantica.
FROM python:3.12-slim

# Sin bytecode, salida sin buffer y cache del modelo en el home del usuario.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/app \
    HF_HOME=/home/app/.cache/huggingface

# Usuario sin privilegios: el proceso no corre como root.
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home \
       --home-dir /home/app --shell /usr/sbin/nologin app

WORKDIR /app

# Las dependencias van antes que el codigo para aprovechar la cache de capas.
COPY requirements.txt ./
# torch primero y con el sufijo +cpu: ese wheel solo existe en el indice CPU.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
       --extra-index-url https://download.pytorch.org/whl/cpu \
       "torch==2.15.0+cpu" \
    && pip install --no-cache-dir -r requirements.txt

# Modelo horneado en la imagen: el contenedor no lo descarga al arrancar.
ARG MODELO_EMBEDDINGS=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
ENV EMBEDDINGS_MODEL=${MODELO_EMBEDDINGS} \
    EMBEDDINGS_DEVICE=cpu \
    LOG_LEVEL=INFO

USER app
RUN python -c "import os; from sentence_transformers import SentenceTransformer; SentenceTransformer(os.environ['EMBEDDINGS_MODEL'], device='cpu')"

# Codigo de la aplicacion (sin tests, scripts, docs ni datos).
COPY --chown=app:app app ./app

EXPOSE 8000

# /health responde 200 incluso degradado; aqui se exige el modelo cargado.
HEALTHCHECK --interval=15s --timeout=5s --start-period=90s --retries=5 \
    CMD python -c "import json, sys, urllib.request; datos = json.load(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)); sys.exit(0 if datos.get('modelo_cargado') is True else 1)"

# Un solo worker: el modelo vive una vez por proceso.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
