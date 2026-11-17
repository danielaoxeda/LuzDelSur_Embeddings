"""Prueba el modelo con descripciones demo del backend, sin pasar por HTTP.

Solo compara pares que comparten sector normalizado y tipo de falla, como el
filtro del motor de agrupacion. No calibra ni cambia umbrales.
"""

import argparse
import csv
import sys
import unicodedata
from collections import defaultdict
from itertools import combinations
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from app.servicio import servicio

UMBRAL_ALTO = 0.55
UMBRAL_BAJO = 0.30
COLUMNAS = ["id", "sector", "tipo_falla", "descripcion", "incidente_esperado"]
RUTA_ENTRADA = RAIZ / "scripts" / "datos" / "semillas_backend.csv"
RUTA_SALIDA = RAIZ / "docs" / "prueba_semillas_pares.csv"


def normalizar_sector(valor: str | None) -> str | None:
    """Replica TextNormalizer.normalizeKey: sin tildes, mayusculas y espacios."""
    if valor is None:
        return None
    sin_tildes = "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", valor)
        if unicodedata.category(caracter) != "Mn"
    )
    limpio = "".join(
        caracter if caracter.isalnum() or caracter == " " else " "
        for caracter in sin_tildes.upper()
    )
    limpio = " ".join(limpio.split())
    return limpio or None


def cargar_filas(ruta: Path) -> list[dict[str, str]]:
    """Lee el CSV y valida que existan las columnas del contrato."""
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        faltantes = [columna for columna in COLUMNAS if columna not in (lector.fieldnames or [])]
        if faltantes:
            raise SystemExit(f"Faltan columnas en {ruta}: {', '.join(faltantes)}")
        filas = [{columna: (fila.get(columna) or "").strip() for columna in COLUMNAS}
                 for fila in lector]
    if not filas:
        raise SystemExit(f"El CSV esta vacio: {ruta}")
    for fila in filas:
        if not fila["id"] or not fila["descripcion"]:
            raise SystemExit("Cada fila necesita id y descripcion")
    return filas


def zona(valor: float) -> str:
    """Clasifica la similitud con los umbrales actuales del backend."""
    if valor >= UMBRAL_ALTO:
        return "alta"
    if valor >= UMBRAL_BAJO:
        return "baja_certeza"
    return "baja"


def etiqueta_par(fila_a: dict[str, str], fila_b: dict[str, str]) -> int | None:
    """1 si ambos declaran el mismo incidente, 0 si difieren, None sin etiqueta."""
    incidente_a = fila_a["incidente_esperado"]
    incidente_b = fila_b["incidente_esperado"]
    if not incidente_a or not incidente_b:
        return None
    return 1 if incidente_a == incidente_b else 0


def construir_pares(filas: list[dict[str, str]]) -> list[dict[str, object]]:
    """Agrupa por sector normalizado y tipo, y arma pares sin repetir."""
    grupos: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for fila in filas:
        sector = normalizar_sector(fila["sector"])
        if sector is None:
            continue
        grupos[(sector, fila["tipo_falla"])].append(fila)

    pares: list[dict[str, object]] = []
    for (sector, tipo), grupo in sorted(grupos.items()):
        for fila_a, fila_b in combinations(grupo, 2):
            pares.append(
                {
                    "sector": sector,
                    "tipo_falla": tipo,
                    "fila_a": fila_a,
                    "fila_b": fila_b,
                }
            )
    return pares


def evaluar(pares: list[dict[str, object]]) -> list[dict[str, object]]:
    """Calcula la similitud de cada par con la funcion del servicio."""
    servicio.cargar()
    if not servicio.modelo_cargado:
        raise SystemExit("El modelo no se pudo cargar")

    evaluados: list[dict[str, object]] = []
    for par in pares:
        fila_a = par["fila_a"]
        fila_b = par["fila_b"]
        valor = servicio.similitud(fila_a["descripcion"], fila_b["descripcion"])
        evaluados.append(
            {
                **par,
                "similitud": valor,
                "zona": zona(valor),
                "etiqueta": etiqueta_par(fila_a, fila_b),
            }
        )
    return evaluados


def metricas(evaluados: list[dict[str, object]]) -> dict[str, int]:
    """Matriz de confusion binaria con corte en 0.55; solo pares etiquetados."""
    tp = fp = tn = fn = 0
    for par in evaluados:
        etiqueta = par["etiqueta"]
        if etiqueta is None:
            continue
        predicho = 1 if float(par["similitud"]) >= UMBRAL_ALTO else 0
        if predicho == 1 and etiqueta == 1:
            tp += 1
        elif predicho == 1 and etiqueta == 0:
            fp += 1
        elif predicho == 0 and etiqueta == 0:
            tn += 1
        else:
            fn += 1
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "aciertos": tp + tn, "etiquetados": tp + fp + tn + fn}


def guardar_csv(evaluados: list[dict[str, object]], ruta: Path) -> None:
    """Exporta todos los pares para auditar cada valor y clasificacion."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    columnas = [
        "id_a", "id_b", "sector", "tipo_falla", "similitud", "zona",
        "incidente_a", "incidente_b", "etiqueta", "prediccion", "correcto",
        "descripcion_a", "descripcion_b",
    ]
    with ruta.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas)
        escritor.writeheader()
        for par in evaluados:
            fila_a = par["fila_a"]
            fila_b = par["fila_b"]
            etiqueta = par["etiqueta"]
            prediccion = 1 if float(par["similitud"]) >= UMBRAL_ALTO else 0
            escritor.writerow(
                {
                    "id_a": fila_a["id"],
                    "id_b": fila_b["id"],
                    "sector": par["sector"],
                    "tipo_falla": par["tipo_falla"],
                    "similitud": f"{float(par['similitud']):.4f}",
                    "zona": par["zona"],
                    "incidente_a": fila_a["incidente_esperado"],
                    "incidente_b": fila_b["incidente_esperado"],
                    "etiqueta": "" if etiqueta is None else etiqueta,
                    "prediccion": prediccion,
                    "correcto": "" if etiqueta is None else int(prediccion == etiqueta),
                    "descripcion_a": fila_a["descripcion"],
                    "descripcion_b": fila_b["descripcion"],
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prueba el modelo con descripciones demo del backend"
    )
    parser.add_argument("--entrada", default=str(RUTA_ENTRADA), help="CSV de reportes demo")
    parser.add_argument("--salida", default=str(RUTA_SALIDA), help="CSV de pares evaluados")
    opciones = parser.parse_args()

    filas = cargar_filas(Path(opciones.entrada))
    pares = construir_pares(filas)
    evaluados = evaluar(pares)

    print("== Prueba con semillas del backend ==")
    print(f"Reportes: {len(filas)}")
    print(f"Pares evaluados (mismo sector y tipo): {len(evaluados)}")

    conteo = {"alta": 0, "baja_certeza": 0, "baja": 0}
    for par in evaluados:
        conteo[str(par["zona"])] += 1
    print("\nPares por zona con los umbrales actuales:")
    print(f"  >= 0.55 (alta):            {conteo['alta']}")
    print(f"  0.30 - 0.55 (baja certeza): {conteo['baja_certeza']}")
    print(f"  < 0.30 (baja):              {conteo['baja']}")

    resultado = metricas(evaluados)
    print("\nPares con etiqueta incidente_esperado:")
    if resultado["etiquetados"] == 0:
        print("  Ninguno: el CSV no trae etiquetas, no se calculan aciertos ni errores.")
    else:
        print(f"  Etiquetados: {resultado['etiquetados']}")
        print(f"  Aciertos: {resultado['aciertos']} "
              f"(TP={resultado['tp']}, TN={resultado['tn']})")
        print(f"  Falsos positivos: {resultado['fp']}")
        print(f"  Falsos negativos: {resultado['fn']}")

    fallidos = [
        par for par in evaluados
        if par["etiqueta"] is not None
        and int(float(par["similitud"]) >= UMBRAL_ALTO) != int(par["etiqueta"])
    ]
    if resultado["etiquetados"] > 0:
        print(f"\nPares mal clasificados (corte 0.55): {len(fallidos)}")
        for par in fallidos:
            fila_a = par["fila_a"]
            fila_b = par["fila_b"]
            tipo = "falso positivo" if float(par["similitud"]) >= UMBRAL_ALTO else "falso negativo"
            print(f"  {fila_a['id']} / {fila_b['id']}  {tipo}  sim={float(par['similitud']):.4f}")
            print(f"    A: {fila_a['descripcion']}")
            print(f"    B: {fila_b['descripcion']}")

    print("\nTodos los pares:")
    for par in evaluados:
        fila_a = par["fila_a"]
        fila_b = par["fila_b"]
        etiqueta = par["etiqueta"]
        texto_etiqueta = "sin etiqueta" if etiqueta is None else (
            "mismo incidente" if etiqueta == 1 else "distinto incidente"
        )
        print(f"  {fila_a['id']} / {fila_b['id']}  sim={float(par['similitud']):.4f} "
              f"zona={par['zona']}  {texto_etiqueta}")
        print(f"    A: {fila_a['descripcion']}")
        print(f"    B: {fila_b['descripcion']}")

    guardar_csv(evaluados, Path(opciones.salida))
    print(f"\nPares exportados: {opciones.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
