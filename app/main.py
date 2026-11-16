"""Aplicacion FastAPI del microservicio de similitud semantica."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.routers.similitud import router
from app.servicio import ModeloNoDisponible, servicio


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Carga el modelo una sola vez; el servicio sigue vivo si falla."""
    servicio.cargar()
    yield


app = FastAPI(
    title="Luz del Sur - Similitud semantica",
    description="Sugiere similitud entre descripciones de fallas electricas.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)


@app.exception_handler(RequestValidationError)
async def validacion_invalida(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    """Devuelve los errores de validación en español."""
    errores: list[dict[str, str]] = []
    for error in exc.errors():
        tipo = error.get("type", "")
        ubicacion = [str(parte) for parte in error.get("loc", ()) if parte != "body"]
        campo = ".".join(ubicacion) or "cuerpo"
        contexto = error.get("ctx") or {}

        if tipo == "string_too_long":
            mensaje = (
                f"El campo {campo} supera el máximo de "
                f"{contexto.get('max_length')} caracteres"
            )
        elif tipo == "too_long":
            mensaje = (
                f"El campo {campo} supera el máximo de "
                f"{contexto.get('max_length')} elementos"
            )
        elif tipo == "missing":
            mensaje = f"Falta el campo obligatorio {campo}"
        elif tipo == "string_type":
            mensaje = f"El campo {campo} debe ser texto"
        elif tipo == "list_type":
            mensaje = f"El campo {campo} debe ser una lista"
        elif tipo == "json_invalid":
            mensaje = "El cuerpo de la petición no es un JSON válido"
        else:
            mensaje = f"El campo {campo} no es válido"

        errores.append({"campo": campo, "mensaje": mensaje})

    return JSONResponse(status_code=422, content={"detail": errores})


@app.exception_handler(ModeloNoDisponible)
async def modelo_no_disponible(
    _: Request, __: ModeloNoDisponible
) -> JSONResponse:
    """Responde 503 sin exponer detalles internos."""
    return JSONResponse(
        status_code=503,
        content={"detail": "Servicio de similitud no disponible"},
    )


@app.get("/health")
def health() -> dict[str, object]:
    """Estado del servicio y del modelo."""
    cargado = servicio.modelo_cargado
    return {
        "estado": "ok" if cargado else "degradado",
        "modelo": servicio.nombre_modelo,
        "modelo_cargado": cargado,
    }
