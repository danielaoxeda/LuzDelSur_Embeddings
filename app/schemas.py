"""Modelos Pydantic del contrato consumido por el backend."""

from typing import Annotated

from pydantic import BaseModel, Field

from app.config import configuracion

Texto = Annotated[str, Field(max_length=configuracion.max_caracteres)]


class SimilitudRequest(BaseModel):
    """Par de textos a comparar."""

    text_a: Texto
    text_b: Texto


class SimilitudResponse(BaseModel):
    """Similitud coseno normalizada entre 0 y 1."""

    similarity: float


class LoteRequest(BaseModel):
    """Texto base y lista de candidatos."""

    text: Texto
    candidates: Annotated[
        list[Texto], Field(max_length=configuracion.max_candidatos)
    ] = Field(default_factory=list)


class LoteResponse(BaseModel):
    """Similitudes en el mismo orden que los candidatos enviados."""

    similarities: list[float]
