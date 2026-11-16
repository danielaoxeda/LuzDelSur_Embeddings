"""Carga unica del modelo y calculo de similitud coseno."""

import re

from sentence_transformers import SentenceTransformer

from app.config import Configuracion, configuracion

_ESPACIOS = re.compile(r"\s+")


def normalizar(texto: str) -> str:
    """Recorta y unifica espacios sin quitar tildes."""
    return _ESPACIOS.sub(" ", texto or "").strip()


def _acotar(valor: float) -> float:
    """Lleva el coseno al rango 0-1 y redondea a 4 decimales."""
    return round(max(0.0, min(1.0, valor)), 4)


class ServicioSimilitud:
    """Mantiene una sola instancia del modelo durante toda la aplicacion."""

    def __init__(self, config: Configuracion) -> None:
        self._config = config
        self._modelo: SentenceTransformer | None = None

    @property
    def nombre_modelo(self) -> str:
        return self._config.modelo

    @property
    def modelo_cargado(self) -> bool:
        return self._modelo is not None

    def cargar(self) -> None:
        """Carga el modelo una vez al iniciar el servicio."""
        if self._modelo is not None:
            return
        self._modelo = SentenceTransformer(
            self._config.modelo, device=self._config.dispositivo
        )
        # Calienta el modelo para que la primera peticion no exceda el timeout.
        self._modelo.encode(["calentamiento"], normalize_embeddings=True)

    def similitud(self, texto_a: str, texto_b: str) -> float:
        """Calcula la similitud coseno entre dos textos."""
        texto_a = normalizar(texto_a)
        texto_b = normalizar(texto_b)
        if not texto_a or not texto_b:
            return 0.0
        vectores = self._modelo.encode(
            [texto_a, texto_b], normalize_embeddings=True, convert_to_numpy=True
        )
        return _acotar(float(vectores[0] @ vectores[1]))

    def similitudes(self, texto: str, candidatos: list[str]) -> list[float]:
        """Calcula la similitud contra cada candidato manteniendo el orden."""
        if not candidatos:
            return []

        texto = normalizar(texto)
        normalizados = [normalizar(candidato) for candidato in candidatos]
        if not texto:
            return [0.0 for _ in candidatos]

        no_vacios = [item for item in normalizados if item]
        if not no_vacios:
            return [0.0 for _ in candidatos]

        vectores = self._modelo.encode(
            [texto, *no_vacios], normalize_embeddings=True, convert_to_numpy=True
        )
        base = vectores[0]
        resultados: list[float] = []
        indice = 1
        for item in normalizados:
            if not item:
                resultados.append(0.0)
                continue
            resultados.append(_acotar(float(base @ vectores[indice])))
            indice += 1
        return resultados


servicio = ServicioSimilitud(configuracion)
