"""Configuracion del servicio leida desde variables de entorno."""

import os

from pydantic import BaseModel

MODELO_POR_DEFECTO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class Configuracion(BaseModel):
    """Parametros de ejecucion del microservicio."""

    modelo: str = os.getenv("EMBEDDINGS_MODEL", MODELO_POR_DEFECTO)
    dispositivo: str = os.getenv("EMBEDDINGS_DEVICE", "cpu")
    max_candidatos: int = int(os.getenv("EMBEDDINGS_MAX_CANDIDATOS", "200"))
    max_caracteres: int = int(os.getenv("EMBEDDINGS_MAX_CARACTERES", "1000"))
    nivel_log: str = os.getenv("LOG_LEVEL", "INFO")


configuracion = Configuracion()
