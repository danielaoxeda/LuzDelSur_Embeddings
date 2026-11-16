"""Aplicacion FastAPI del microservicio de similitud semantica."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers.similitud import router
from app.servicio import servicio


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Carga el modelo una sola vez al arrancar el servicio."""
    servicio.cargar()
    yield


app = FastAPI(
    title="Luz del Sur - Similitud semantica",
    description="Sugiere similitud entre descripciones de fallas electricas.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/health")
def health() -> dict[str, object]:
    """Estado del servicio y del modelo."""
    return {
        "estado": "ok",
        "modelo": servicio.nombre_modelo,
        "modelo_cargado": servicio.modelo_cargado,
    }
