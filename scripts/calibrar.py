"""Calibra los umbrales del servicio con pares sinteticos etiquetados."""

import argparse
import csv
import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import roc_auc_score
from sklearn.metrics.pairwise import cosine_similarity

from app.servicio import servicio

RUTA_PARES = RAIZ / "scripts" / "datos" / "pares_calibracion.csv"
RUTA_PARTICIONES = RAIZ / "scripts" / "datos" / "particiones_calibracion.csv"
RUTA_RESULTADOS = RAIZ / "docs" / "calibracion_resultados.csv"
RUTA_PARES_EVALUADOS = RAIZ / "docs" / "calibracion_pares.csv"
RUTA_FIG_DISTRIBUCION = RAIZ / "docs" / "calibracion_distribucion.png"
RUTA_FIG_UMBRALES = RAIZ / "docs" / "calibracion_umbrales.png"

SEMILLA = 20261116
UMBRAL_ACTUAL_ALTO = 0.55
UMBRAL_ACTUAL_BAJO = 0.30
UMBRALES = [round(0.20 + 0.05 * paso, 2) for paso in range(15)]
PRECISION_MINIMA = 0.90
EXHAUSTIVIDAD_MINIMA = 0.95


def cargar_pares(ruta: Path) -> list[dict[str, object]]:
    """Lee los pares y convierte la etiqueta a entero."""
    with ruta.open(encoding="utf-8", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    for fila in filas:
        fila["misma_falla"] = int(str(fila["misma_falla"]))
    return filas


def dividir_pares(
    pares: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Divide 30/30 de forma estratificada con semilla fija."""
    azar = random.Random(SEMILLA)
    calibracion: list[dict[str, object]] = []
    evaluacion: list[dict[str, object]] = []
    for etiqueta in (1, 0):
        grupo = [fila for fila in pares if fila["misma_falla"] == etiqueta]
        azar.shuffle(grupo)
        calibracion.extend(grupo[:15])
        evaluacion.extend(grupo[15:])
    calibracion.sort(key=lambda fila: str(fila["id"]))
    evaluacion.sort(key=lambda fila: str(fila["id"]))
    return calibracion, evaluacion


def guardar_particiones(
    calibracion: list[dict[str, object]], evaluacion: list[dict[str, object]]
) -> None:
    """Guarda la division para que sea reproducible y auditable."""
    RUTA_PARTICIONES.parent.mkdir(parents=True, exist_ok=True)
    with RUTA_PARTICIONES.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["id", "particion"])
        for fila in sorted(calibracion, key=lambda item: str(item["id"])):
            escritor.writerow([fila["id"], "calibracion"])
        for fila in sorted(evaluacion, key=lambda item: str(item["id"])):
            escritor.writerow([fila["id"], "evaluacion"])


def similitudes_embeddings(pares: list[dict[str, object]]) -> dict[str, float]:
    """Usa la misma funcion del servicio, sin pasar por HTTP."""
    servicio.cargar()
    if not servicio.modelo_cargado:
        raise RuntimeError("El modelo no se pudo cargar")
    return {
        str(fila["id"]): servicio.similitud(
            str(fila["texto_a"]), str(fila["texto_b"])
        )
        for fila in pares
    }


def similitudes_tfidf(pares: list[dict[str, object]]) -> dict[str, float]:
    """Calcula TF-IDF con unigramas y bigramas sobre todo el corpus."""
    vectorizador = TfidfVectorizer(
        ngram_range=(1, 2), strip_accents=None, stop_words=None, lowercase=True
    )
    textos: list[str] = []
    for fila in pares:
        textos.extend([str(fila["texto_a"]), str(fila["texto_b"])])
    matriz = vectorizador.fit_transform(textos)

    resultados: dict[str, float] = {}
    for indice, fila in enumerate(pares):
        vector_a = matriz[2 * indice]
        vector_b = matriz[2 * indice + 1]
        resultados[str(fila["id"])] = float(cosine_similarity(vector_a, vector_b)[0, 0])
    return resultados


def metricas(
    etiquetas: list[int], valores: list[float], umbral: float
) -> dict[str, float | int]:
    """Precision, exhaustividad, F1 y matriz de confusion a un umbral."""
    tp = fp = tn = fn = 0
    for etiqueta, valor in zip(etiquetas, valores):
        prediccion = 1 if valor >= umbral else 0
        if prediccion == 1 and etiqueta == 1:
            tp += 1
        elif prediccion == 1 and etiqueta == 0:
            fp += 1
        elif prediccion == 0 and etiqueta == 0:
            tn += 1
        else:
            fn += 1

    precision = tp / (tp + fp) if tp + fp else 0.0
    exhaustividad = tp / (tp + fn) if tp + fn else 0.0
    f1 = (
        2 * precision * exhaustividad / (precision + exhaustividad)
        if precision + exhaustividad
        else 0.0
    )
    return {
        "umbral": umbral,
        "precision": precision,
        "recall": exhaustividad,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }


def barrer_umbrales(
    etiquetas: list[int], valores: list[float]
) -> list[dict[str, float | int]]:
    """Evalua todos los umbrales del rango de calibracion."""
    return [metricas(etiquetas, valores, umbral) for umbral in UMBRALES]


def proponer_umbrales(
    barrido: list[dict[str, float | int]],
) -> tuple[float, float, str, str]:
    """Aplica las reglas de precision y exhaustividad sobre calibracion."""
    altos = [fila for fila in barrido if float(fila["precision"]) >= PRECISION_MINIMA]
    if altos:
        umbral_alto = float(min(altos, key=lambda fila: float(fila["umbral"]))["umbral"])
        origen_alto = "regla_precision"
    else:
        mejor = max(barrido, key=lambda fila: float(fila["f1"]))
        umbral_alto = float(mejor["umbral"])
        origen_alto = "respaldo_mejor_f1"

    bajos = [fila for fila in barrido if float(fila["recall"]) >= EXHAUSTIVIDAD_MINIMA]
    if bajos:
        umbral_bajo = float(max(bajos, key=lambda fila: float(fila["umbral"]))["umbral"])
        origen_bajo = "regla_exhaustividad"
    else:
        umbral_bajo = float(min(UMBRALES))
        origen_bajo = "respaldo_umbral_minimo"
    return umbral_alto, umbral_bajo, origen_alto, origen_bajo


def auc(etiquetas: list[int], valores: list[float]) -> float:
    """AUC por Mann-Whitney; una sola clase devuelve 0.5."""
    if len(set(etiquetas)) < 2:
        return 0.5
    return float(roc_auc_score(etiquetas, valores))


def evaluar_modelo(
    nombre: str,
    etiquetas: list[int],
    valores: list[float],
    umbrales: list[tuple[str, float]],
    barrido: list[dict[str, float | int]],
) -> list[dict[str, object]]:
    """Filas de evaluacion y AUC para el CSV de resultados."""
    filas: list[dict[str, object]] = []
    for tipo, umbral in umbrales:
        fila = metricas(etiquetas, valores, umbral)
        filas.append(
            {
                "modelo": nombre,
                "particion": "evaluacion",
                "tipo": tipo,
                **fila,
                "auc": "",
            }
        )
    filas.append(
        {
            "modelo": nombre,
            "particion": "evaluacion",
            "tipo": "auc",
            "umbral": "",
            "precision": "",
            "recall": "",
            "f1": "",
            "tp": "",
            "fp": "",
            "tn": "",
            "fn": "",
            "auc": auc(etiquetas, valores),
        }
    )
    for fila in barrido:
        filas.append(
            {
                "modelo": nombre,
                "particion": "calibracion",
                "tipo": "barrido",
                **fila,
                "auc": "",
            }
        )
    return filas


def guardar_resultados(filas: list[dict[str, object]]) -> None:
    """Escribe el CSV numerico completo y reproducible."""
    RUTA_RESULTADOS.parent.mkdir(parents=True, exist_ok=True)
    columnas = [
        "modelo",
        "particion",
        "tipo",
        "umbral",
        "precision",
        "recall",
        "f1",
        "tp",
        "fp",
        "tn",
        "fn",
        "auc",
    ]
    with RUTA_RESULTADOS.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas)
        escritor.writeheader()
        for fila in filas:
            escritor.writerow(fila)


def guardar_pares_evaluados(
    pares: list[dict[str, object]],
    valores_emb: dict[str, float],
    valores_tfidf: dict[str, float],
) -> None:
    """Exporta la similitud de cada par para auditar cualquier umbral."""
    columnas = [
        "id",
        "particion",
        "escenario",
        "texto_a",
        "texto_b",
        "misma_falla",
        "sim_embeddings",
        "sim_tfidf",
    ]
    with RUTA_PARES_EVALUADOS.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas)
        escritor.writeheader()
        for fila in pares:
            identificador = str(fila["id"])
            escritor.writerow(
                {
                    "id": identificador,
                    "particion": fila["particion"],
                    "escenario": fila["escenario"],
                    "texto_a": fila["texto_a"],
                    "texto_b": fila["texto_b"],
                    "misma_falla": fila["misma_falla"],
                    "sim_embeddings": f"{valores_emb[identificador]:.4f}",
                    "sim_tfidf": f"{valores_tfidf[identificador]:.4f}",
                }
            )


def graficar_distribucion(
    pares: list[dict[str, object]],
    valores: dict[str, float],
    umbral_alto: float,
    umbral_bajo: float,
) -> None:
    """Histograma de similitudes para pares iguales y distintos."""
    iguales = [valores[str(f["id"])] for f in pares if f["misma_falla"] == 1]
    distintos = [valores[str(f["id"])] for f in pares if f["misma_falla"] == 0]
    bins = np.arange(0.0, 1.05, 0.05)

    figura, eje = plt.subplots(figsize=(9, 5))
    eje.hist(iguales, bins=bins, alpha=0.6, label="Misma falla", color="#2a9d8f")
    eje.hist(distintos, bins=bins, alpha=0.6, label="Falla distinta", color="#e76f51")
    for valor, color, texto in (
        (umbral_alto, "#264653", f"Alto {umbral_alto:.2f}"),
        (umbral_bajo, "#f4a261", f"Bajo {umbral_bajo:.2f}"),
    ):
        eje.axvline(valor, color=color, linestyle="--", linewidth=1.5, label=texto)
    eje.set_xlabel("Similitud coseno")
    eje.set_ylabel("Cantidad de pares")
    eje.set_title("Distribucion de similitudes (60 pares sinteticos)")
    eje.legend()
    figura.tight_layout()
    figura.savefig(RUTA_FIG_DISTRIBUCION, dpi=150)
    plt.close(figura)


def graficar_umbrales(
    barridos: dict[str, list[dict[str, float | int]]],
) -> None:
    """Precision y exhaustividad en calibracion para ambos modelos."""
    figura, eje = plt.subplots(figsize=(9, 5))
    estilos = {"embeddings": "-", "tfidf": "--"}
    colores = {"precision": "#264653", "recall": "#e76f51"}
    for modelo, barrido in barridos.items():
        umbrales = [float(fila["umbral"]) for fila in barrido]
        for metrica, color in colores.items():
            eje.plot(
                umbrales,
                [float(fila[metrica]) for fila in barrido],
                estilos[modelo],
                color=color,
                alpha=0.9 if modelo == "embeddings" else 0.55,
                label=f"{metrica} {modelo}",
            )
    eje.axhline(PRECISION_MINIMA, color="#264653", linestyle=":", linewidth=1)
    eje.axhline(EXHAUSTIVIDAD_MINIMA, color="#e76f51", linestyle=":", linewidth=1)
    eje.set_xlabel("Umbral de similitud")
    eje.set_ylabel("Valor")
    eje.set_ylim(0.0, 1.05)
    eje.set_title("Precision y exhaustividad en calibracion")
    eje.legend(fontsize=8, ncol=2)
    figura.tight_layout()
    figura.savefig(RUTA_FIG_UMBRALES, dpi=150)
    plt.close(figura)


def imprimir_tabla(titulo: str, filas: list[dict[str, float | int]]) -> None:
    """Muestra una tabla compacta por consola."""
    print(f"\n{titulo}")
    print(f"{'Umbral':>7}{'Prec.':>9}{'Exh.':>8}{'F1':>8}{'TP':>5}{'FP':>5}{'TN':>5}{'FN':>5}")
    for fila in filas:
        print(
            f"{float(fila['umbral']):>7.2f}{float(fila['precision']):>9.2f}"
            f"{float(fila['recall']):>8.2f}{float(fila['f1']):>8.2f}"
            f"{int(fila['tp']):>5}{int(fila['fp']):>5}"
            f"{int(fila['tn']):>5}{int(fila['fn']):>5}"
        )


def pares_fallidos(
    pares: list[dict[str, object]], valores: dict[str, float], umbral: float
) -> list[tuple[dict[str, object], float, str]]:
    """Lista falsos positivos y falsos negativos de la evaluacion."""
    fallidos = []
    for fila in pares:
        valor = valores[str(fila["id"])]
        predicho = 1 if valor >= umbral else 0
        if predicho != int(fila["misma_falla"]):
            tipo = "falso_positivo" if predicho == 1 else "falso_negativo"
            fallidos.append((fila, valor, tipo))
    return fallidos


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibra umbrales de similitud")
    parser.add_argument(
        "--pares", default=str(RUTA_PARES), help="CSV de pares etiquetados"
    )
    opciones = parser.parse_args()

    pares = cargar_pares(Path(opciones.pares))
    if len(pares) != 60 or sum(int(f["misma_falla"]) for f in pares) != 30:
        raise SystemExit("Se esperaban 60 pares con 30 etiquetas positivas")

    calibracion, evaluacion = dividir_pares(pares)
    guardar_particiones(calibracion, evaluacion)
    for fila in calibracion:
        fila["particion"] = "calibracion"
    for fila in evaluacion:
        fila["particion"] = "evaluacion"

    print("Calculando similitudes con embeddings...")
    valores_emb = similitudes_embeddings(pares)
    print("Calculando similitudes con TF-IDF...")
    valores_tfidf = similitudes_tfidf(pares)

    etiquetas_cal = [int(f["misma_falla"]) for f in calibracion]
    etiquetas_eval = [int(f["misma_falla"]) for f in evaluacion]
    emb_cal = [valores_emb[str(f["id"])] for f in calibracion]
    emb_eval = [valores_emb[str(f["id"])] for f in evaluacion]
    tfidf_cal = [valores_tfidf[str(f["id"])] for f in calibracion]
    tfidf_eval = [valores_tfidf[str(f["id"])] for f in evaluacion]

    barrido_emb = barrer_umbrales(etiquetas_cal, emb_cal)
    barrido_tfidf = barrer_umbrales(etiquetas_cal, tfidf_cal)

    alto_emb, bajo_emb, origen_alto_emb, origen_bajo_emb = proponer_umbrales(
        barrido_emb
    )
    alto_tfidf, bajo_tfidf, origen_alto_tfidf, origen_bajo_tfidf = proponer_umbrales(
        barrido_tfidf
    )

    print(f"\nUmbral alto embeddings: {alto_emb:.2f} ({origen_alto_emb})")
    print(f"Umbral bajo embeddings: {bajo_emb:.2f} ({origen_bajo_emb})")
    print(f"Umbral alto TF-IDF: {alto_tfidf:.2f} ({origen_alto_tfidf})")
    print(f"Umbral bajo TF-IDF: {bajo_tfidf:.2f} ({origen_bajo_tfidf})")

    imprimir_tabla("Barrido de calibracion (embeddings)", barrido_emb)
    imprimir_tabla("Barrido de calibracion (TF-IDF)", barrido_tfidf)

    puntos_emb = [
        ("propuesto_alto", alto_emb),
        ("propuesto_bajo", bajo_emb),
        ("actual_0.55", UMBRAL_ACTUAL_ALTO),
        ("actual_0.30", UMBRAL_ACTUAL_BAJO),
    ]
    puntos_tfidf = [
        ("propuesto_alto", alto_tfidf),
        ("propuesto_bajo", bajo_tfidf),
        ("actual_0.55", UMBRAL_ACTUAL_ALTO),
        ("actual_0.30", UMBRAL_ACTUAL_BAJO),
    ]

    filas_eval_emb = [
        metricas(etiquetas_eval, emb_eval, umbral) | {"tipo": tipo}
        for tipo, umbral in puntos_emb
    ]
    filas_eval_tfidf = [
        metricas(etiquetas_eval, tfidf_eval, umbral) | {"tipo": tipo}
        for tipo, umbral in puntos_tfidf
    ]
    imprimir_tabla("Evaluacion (embeddings)", filas_eval_emb)
    imprimir_tabla("Evaluacion (TF-IDF)", filas_eval_tfidf)

    print(f"\nAUC embeddings: calibracion={auc(etiquetas_cal, emb_cal):.3f} "
          f"evaluacion={auc(etiquetas_eval, emb_eval):.3f}")
    print(f"AUC TF-IDF: calibracion={auc(etiquetas_cal, tfidf_cal):.3f} "
          f"evaluacion={auc(etiquetas_eval, tfidf_eval):.3f}")

    for nombre, valores, umbral in (
        ("embeddings", valores_emb, alto_emb),
        ("tfidf", valores_tfidf, alto_tfidf),
    ):
        fallidos = pares_fallidos(evaluacion, valores, umbral)
        print(f"\nPares mal clasificados ({nombre}, umbral {umbral:.2f}): {len(fallidos)}")
        for fila, valor, tipo in fallidos:
            print(
                f"  {fila['id']} {tipo:<14} sim={valor:.4f} "
                f"escenario={fila['escenario']} | {fila['texto_a']} / {fila['texto_b']}"
            )

    intermedios = [
        f
        for f in evaluacion
        if bajo_emb <= valores_emb[str(f["id"])] < alto_emb
    ]
    print(
        f"\nZona de baja certeza (embeddings, [{bajo_emb:.2f}, {alto_emb:.2f})): "
        f"{len(intermedios)} de {len(evaluacion)} pares de evaluacion"
    )

    filas: list[dict[str, object]] = []
    filas.extend(
        evaluar_modelo("embeddings", etiquetas_eval, emb_eval, puntos_emb, barrido_emb)
    )
    filas.extend(
        evaluar_modelo("tfidf", etiquetas_eval, tfidf_eval, puntos_tfidf, barrido_tfidf)
    )
    filas.append(
        {
            "modelo": "embeddings",
            "particion": "calibracion",
            "tipo": "auc",
            "umbral": "",
            "precision": "",
            "recall": "",
            "f1": "",
            "tp": "",
            "fp": "",
            "tn": "",
            "fn": "",
            "auc": auc(etiquetas_cal, emb_cal),
        }
    )
    filas.append(
        {
            "modelo": "tfidf",
            "particion": "calibracion",
            "tipo": "auc",
            "umbral": "",
            "precision": "",
            "recall": "",
            "f1": "",
            "tp": "",
            "fp": "",
            "tn": "",
            "fn": "",
            "auc": auc(etiquetas_cal, tfidf_cal),
        }
    )
    guardar_resultados(filas)
    guardar_pares_evaluados(pares, valores_emb, valores_tfidf)

    graficar_distribucion(pares, valores_emb, alto_emb, bajo_emb)
    graficar_umbrales({"embeddings": barrido_emb, "tfidf": barrido_tfidf})

    print(f"\nParticiones: {RUTA_PARTICIONES}")
    print(f"Resultados: {RUTA_RESULTADOS}")
    print(f"Pares evaluados: {RUTA_PARES_EVALUADOS}")
    print(f"Figuras: {RUTA_FIG_DISTRIBUCION} y {RUTA_FIG_UMBRALES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
