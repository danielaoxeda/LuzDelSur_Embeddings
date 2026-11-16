"""Mide la latencia del microservicio con httpx contra el servidor local."""

import argparse
import ctypes
import os
import platform
import statistics
import time
from datetime import datetime
from pathlib import Path

import httpx
import torch

RAIZ = Path(__file__).resolve().parent.parent
TIMEOUT_BACKEND_MS = 1500.0

TEXTO_BASE = "Se escuchó una explosión y se apagó toda mi cuadra"
TEXTOS = [
    "No hay luz en toda la cuadra desde hace 20 minutos",
    "Sonó un fuerte ruido del transformador y no hay luz",
    "Mi luz parpadea solo en mi casa",
    "La tensión baja y los focos se ven tenues",
    "El medidor hace un ruido raro y no registra consumo",
    "Se cayó un poste y hay cables en la pista",
    "Toda la manzana quedó sin energía",
    "El alumbrado público no enciende desde ayer",
    "Hay un olor a quemado cerca del medidor",
    "La luz se va y vuelve cada pocos minutos",
]


class EstadoMemoria(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def ram_gb() -> float:
    """RAM total aproximada, sin dependencias externas."""
    if os.name == "nt":
        estado = EstadoMemoria()
        estado.dwLength = ctypes.sizeof(EstadoMemoria)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(estado))
        return estado.ullTotalPhys / (1024**3)
    try:
        with open("/proc/meminfo", encoding="utf-8") as archivo:
            linea = archivo.readline()
        return int(linea.split()[1]) / (1024**2)
    except OSError:
        return 0.0


def candidatos(cantidad: int) -> list[str]:
    """Genera candidatos distintos y dentro del limite de caracteres."""
    return [f"{TEXTOS[i % len(TEXTOS)]} (reporte {i + 1})" for i in range(cantidad)]


def percentil(valores: list[float], proporcion: float) -> float:
    ordenados = sorted(valores)
    posicion = (len(ordenados) - 1) * proporcion
    inferior = int(posicion)
    superior = min(inferior + 1, len(ordenados) - 1)
    fraccion = posicion - inferior
    return ordenados[inferior] + (ordenados[superior] - ordenados[inferior]) * fraccion


def medir(cliente: httpx.Client, ruta: str, cuerpo: dict, repeticiones: int) -> list[float]:
    tiempos: list[float] = []
    for _ in range(repeticiones):
        inicio = time.perf_counter()
        respuesta = cliente.post(ruta, json=cuerpo)
        respuesta.raise_for_status()
        tiempos.append((time.perf_counter() - inicio) * 1000)
    return tiempos


def main() -> int:
    parser = argparse.ArgumentParser(description="Mide latencia del microservicio")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--repeticiones", type=int, default=30)
    parser.add_argument("--salida", default=str(RAIZ / "docs" / "latencia.md"))
    opciones = parser.parse_args()

    escenarios = [
        ("/api/v1/similarity", "/api/v1/similarity", {"text_a": TEXTO_BASE, "text_b": TEXTOS[1]}),
        ("batch 10", "/api/v1/similarity/batch", {"text": TEXTO_BASE, "candidates": candidatos(10)}),
        ("batch 50", "/api/v1/similarity/batch", {"text": TEXTO_BASE, "candidates": candidatos(50)}),
        ("batch 200", "/api/v1/similarity/batch", {"text": TEXTO_BASE, "candidates": candidatos(200)}),
    ]

    with httpx.Client(base_url=opciones.url, timeout=60.0, trust_env=False) as cliente:
        salud = cliente.get("/health")
        salud.raise_for_status()
        modelo = salud.json().get("modelo", "desconocido")

        # Calentamiento: dos peticiones por escenario antes de medir.
        for _, ruta, cuerpo in escenarios:
            for _ in range(2):
                cliente.post(ruta, json=cuerpo).raise_for_status()

        resultados = []
        for nombre, ruta, cuerpo in escenarios:
            tiempos = medir(cliente, ruta, cuerpo, opciones.repeticiones)
            resultados.append(
                {
                    "nombre": nombre,
                    "p50": percentil(tiempos, 0.50),
                    "p95": percentil(tiempos, 0.95),
                    "maximo": max(tiempos),
                    "media": statistics.mean(tiempos),
                }
            )

    print(f"\nLatencia con {opciones.repeticiones} repeticiones por escenario\n")
    print(f"{'Escenario':<14}{'p50 (ms)':>10}{'p95 (ms)':>10}{'max (ms)':>10}{'margen p95':>12}")
    for fila in resultados:
        margen = TIMEOUT_BACKEND_MS - fila["p95"]
        print(
            f"{fila['nombre']:<14}{fila['p50']:>10.1f}{fila['p95']:>10.1f}"
            f"{fila['maximo']:>10.1f}{margen:>12.1f}"
        )

    margen_global = TIMEOUT_BACKEND_MS - max(fila["p95"] for fila in resultados)
    veredicto = (
        "Hay margen frente al timeout de 1,5 s del backend."
        if margen_global > 0
        else "No hay margen: algun p95 supera el timeout de 1,5 s del backend."
    )
    print(f"\n{veredicto} Margen minimo (p95): {margen_global:.1f} ms")

    fecha = datetime.now().astimezone().isoformat(timespec="seconds")
    lineas = [
        "# Latencia del microservicio de similitud",
        "",
        f"- Fecha: {fecha}",
        f"- Máquina: {platform.node()} ({platform.system()} {platform.release()})",
        f"- CPU: {platform.processor() or 'no informada'} ({os.cpu_count()} núcleos lógicos)",
        f"- RAM: {ram_gb():.1f} GB",
        f"- Python: {platform.python_version()}",
        f"- torch: {torch.__version__}",
        f"- Modelo: {modelo}",
        f"- Servidor: {opciones.url}",
        f"- Repeticiones por escenario: {opciones.repeticiones}",
        f"- Timeout del backend: {TIMEOUT_BACKEND_MS:.0f} ms",
        "",
        "| Escenario | p50 (ms) | p95 (ms) | máx (ms) | media (ms) | margen p95 (ms) |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for fila in resultados:
        lineas.append(
            f"| {fila['nombre']} | {fila['p50']:.1f} | {fila['p95']:.1f} | "
            f"{fila['maximo']:.1f} | {fila['media']:.1f} | "
            f"{TIMEOUT_BACKEND_MS - fila['p95']:.1f} |"
        )
    lineas.extend(["", veredicto, ""])

    salida = Path(opciones.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text("\n".join(lineas), encoding="utf-8")
    print(f"Resultado guardado en {salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
