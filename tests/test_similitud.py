"""Pruebas del contrato de similitud."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.servicio import servicio

TEXTO_A = "Se escuchó una explosión y se apagó toda mi cuadra"
TEXTO_B = "Sonó un fuerte ruido del transformador y no hay luz"
TEXTO_C = "Mi luz parpadea solo en mi casa"


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
    assert pedir_similitud(cliente, TEXTO_A, TEXTO_B) >= 0.55


def test_textos_distintos_dan_similitud_baja(cliente: TestClient) -> None:
    assert pedir_similitud(cliente, TEXTO_A, TEXTO_C) <= 0.45


def test_texto_vacio_devuelve_cero(cliente: TestClient) -> None:
    assert pedir_similitud(cliente, "   ", "No hay luz en la cuadra") == 0.0


def test_lote_devuelve_tres_similitudes(cliente: TestClient) -> None:
    respuesta = cliente.post(
        "/api/v1/similarity/batch",
        json={"text": TEXTO_A, "candidates": [TEXTO_B, TEXTO_C, "Sin energía"]},
    )
    assert respuesta.status_code == 200
    similitudes = respuesta.json()["similarities"]
    assert len(similitudes) == 3
    assert all(0.0 <= valor <= 1.0 for valor in similitudes)


def test_lote_vacio_devuelve_lista_vacia(cliente: TestClient) -> None:
    respuesta = cliente.post(
        "/api/v1/similarity/batch", json={"text": TEXTO_A, "candidates": []}
    )
    assert respuesta.status_code == 200
    assert respuesta.json() == {"similarities": []}


def test_texto_de_1000_caracteres_es_aceptado(cliente: TestClient) -> None:
    texto = "No hay luz en la cuadra. " * 40
    texto = texto[:1000]
    respuesta = cliente.post(
        "/api/v1/similarity", json={"text_a": texto, "text_b": TEXTO_A}
    )
    assert respuesta.status_code == 200


def test_texto_de_1001_caracteres_devuelve_422(cliente: TestClient) -> None:
    respuesta = cliente.post(
        "/api/v1/similarity", json={"text_a": "a" * 1001, "text_b": TEXTO_A}
    )
    assert respuesta.status_code == 422
    mensaje = respuesta.json()["detail"][0]["mensaje"]
    assert "1000" in mensaje and "text_a" in mensaje


def test_mas_de_200_candidatos_devuelve_422(cliente: TestClient) -> None:
    respuesta = cliente.post(
        "/api/v1/similarity/batch",
        json={"text": TEXTO_A, "candidates": ["Corte de luz"] * 201},
    )
    assert respuesta.status_code == 422
    mensaje = respuesta.json()["detail"][0]["mensaje"]
    assert "200" in mensaje and "candidates" in mensaje


def test_campos_faltantes_o_tipo_erroneo_devuelven_422(
    cliente: TestClient,
) -> None:
    faltante = cliente.post("/api/v1/similarity", json={"text_a": TEXTO_A})
    assert faltante.status_code == 422
    assert "obligatorio" in faltante.json()["detail"][0]["mensaje"]

    tipo_erroneo = cliente.post(
        "/api/v1/similarity", json={"text_a": 123, "text_b": TEXTO_A}
    )
    assert tipo_erroneo.status_code == 422
    assert "texto" in tipo_erroneo.json()["detail"][0]["mensaje"]


def test_el_orden_del_lote_coincide_con_las_similitudes(
    cliente: TestClient,
) -> None:
    candidatos = [TEXTO_B, TEXTO_C, "No hay luz en toda la cuadra"]
    respuesta = cliente.post(
        "/api/v1/similarity/batch",
        json={"text": TEXTO_A, "candidates": candidatos},
    )
    similitudes = respuesta.json()["similarities"]
    for candidato, valor in zip(candidatos, similitudes):
        individual = pedir_similitud(cliente, TEXTO_A, candidato)
        assert abs(valor - individual) <= 0.02


def test_modelo_no_cargado_devuelve_503(cliente: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(servicio, "_modelo", None)

    salud = cliente.get("/health")
    assert salud.status_code == 200
    assert salud.json()["modelo_cargado"] is False

    simple = cliente.post(
        "/api/v1/similarity", json={"text_a": TEXTO_A, "text_b": TEXTO_B}
    )
    assert simple.status_code == 503
    assert simple.json()["detail"] == "Servicio de similitud no disponible"

    lote = cliente.post(
        "/api/v1/similarity/batch",
        json={"text": TEXTO_A, "candidates": [TEXTO_B]},
    )
    assert lote.status_code == 503
    assert lote.json()["detail"] == "Servicio de similitud no disponible"
