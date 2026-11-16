"""Endpoints de similitud compatibles con el backend."""

from fastapi import APIRouter, Request

from app.schemas import (
    LoteRequest,
    LoteResponse,
    SimilitudRequest,
    SimilitudResponse,
)
from app.servicio import servicio

router = APIRouter(prefix="/api/v1", tags=["similitud"])


@router.post("/similarity", response_model=SimilitudResponse)
def similitud_simple(peticion: SimilitudRequest) -> SimilitudResponse:
    """Calcula la similitud entre dos textos."""
    return SimilitudResponse(
        similarity=servicio.similitud(peticion.text_a, peticion.text_b)
    )


@router.post("/similarity/batch", response_model=LoteResponse)
def similitud_por_lote(peticion: LoteRequest, request: Request) -> LoteResponse:
    """Calcula la similitud contra cada candidato."""
    # Solo se guarda la cantidad; nunca el contenido de los textos.
    request.state.candidatos = len(peticion.candidates)
    return LoteResponse(
        similarities=servicio.similitudes(peticion.text, peticion.candidates)
    )
