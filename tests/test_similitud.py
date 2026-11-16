"""Pruebas del contrato de similitud."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def cliente():
    """Levanta la app una vez y reutiliza el modelo cargado."""
    with TestClient(app) as cliente_pruebas:
        yield cliente_pruebas


def pedir_similitud(cliente: TestClient, texto_a: str, texto_b: str) -> float:
    respuesta = cliente.post(
        "/api/v1/similarity", json={"text_a": texto_a, "text_b": texto_b}
    )
    assert respuesta.status_code == 200
    return respuesta.json()["similarity"]


def test_textos_casi_iguales_dan_similitud_alta(cliente: TestClient) -> None:
    valor = pedir_similitud(
        cliente,
        "Se escuchó una explosión y se apagó toda mi cuadra",
        "Sonó un fuerte ruido del transformador y no hay luz",
    )
    assert valor >= 0.55


def test_textos_distintos_dan_similitud_baja(cliente: TestClient) -> None:
    valor = pedir_similitud(
        cliente,
        "Se escuchó una explosión y se apagó toda mi cuadra",
        "Mi luz parpadea solo en mi casa",
    )
    assert valor <= 0.45


def test_texto_vacio_devuelve_cero(cliente: TestClient) -> None:
    respuesta = cliente.post(
        "/api/v1/similarity",
        json={"text_a": "   ", "text_b": "No hay luz en la cuadra"},
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["similarity"] == 0.0


def test_lote_devuelve_tres_similitudes_en_orden(cliente: TestClient) -> None:
    respuesta = cliente.post(
        "/api/v1/similarity/batch",
        json={
            "text": "Se escuchó una explosión y se apagó toda mi cuadra",
            "candidates": [
                "Sonó un fuerte ruido del transformador y no hay luz",
                "Mi luz parpadea solo en mi casa",
                "No hay luz en toda la cuadra",
            ],
        },
    )
    assert respuesta.status_code == 200
    similitudes = respuesta.json()["similarities"]
    assert len(similitudes) == 3
    assert all(0.0 <= valor <= 1.0 for valor in similitudes)
    assert similitudes[0] > similitudes[1]
