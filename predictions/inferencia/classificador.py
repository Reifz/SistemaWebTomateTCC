"""Inferência do classificador MobileNetV2 V5."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True


@dataclass
class ResultadoClassificacao:
    caminho_imagem: str

    classe_prevista: str

    confianca: float

    confianca_percentual: float

    nivel_confianca: str

    tempo_inferencia_ms: int

    principais_predicoes: list[dict[str, float | str]]

    todas_probabilidades: dict[str, float]


def carregar_classes(caminho: str | Path) -> list[str]:
    arquivo = Path(caminho)

    if not arquivo.is_file():
        raise FileNotFoundError(f"Arquivo de classes não encontrado: {arquivo}")

    classes = [linha.strip() for linha in arquivo.read_text(encoding="utf-8").splitlines() if linha.strip()]

    if not classes:
        raise ValueError("O arquivo de classes está vazio.")

    return classes


def carregar_modelo(caminho: str | Path) -> Any:
    """Carrega o artefato confiável após a verificação de integridade."""

    arquivo = Path(caminho)

    if not arquivo.is_file():
        raise FileNotFoundError(f"Modelo de predição não encontrado: {arquivo}")

    import tensorflow as tf
    from tensorflow.keras.applications.mobilenet_v2 import preprocess_input

    objetos_personalizados = {
        "preprocess_input": preprocess_input,
        "function": preprocess_input,
    }

    try:
        return tf.keras.models.load_model(
            str(arquivo),
            compile=False,
            custom_objects=objetos_personalizados,
            safe_mode=False,
        )
    except TypeError:
        return tf.keras.models.load_model(
            str(arquivo),
            compile=False,
            custom_objects=objetos_personalizados,
        )


def tamanho_entrada(modelo: Any, padrao: int = 224) -> tuple[int, int]:
    try:
        formato = modelo.input_shape[0] if isinstance(modelo.input_shape, list) else modelo.input_shape

        if formato[1] and formato[2]:
            return int(formato[1]), int(formato[2])
    except (AttributeError, IndexError, TypeError):
        pass

    return padrao, padrao


def carregar_matriz_imagem(caminho: str | Path, tamanho: tuple[int, int]) -> np.ndarray:
    arquivo = Path(caminho)

    if not arquivo.is_file():
        raise FileNotFoundError(f"Imagem não encontrada: {arquivo}")

    altura, largura = tamanho

    with Image.open(arquivo) as imagem:
        imagem = imagem.convert("RGB").resize((largura, altura), Image.Resampling.BILINEAR)

        matriz = np.asarray(imagem, dtype=np.float32)

    # O modelo V5 já contém a camada de pré-processamento da MobileNetV2.
    return np.expand_dims(matriz, axis=0)


def normalizar_probabilidades(valores: np.ndarray) -> np.ndarray:
    probabilidades = np.asarray(valores, dtype=np.float64).reshape(-1)

    soma = float(probabilidades.sum())

    if np.any(probabilidades < 0) or not 0.98 <= soma <= 1.02:
        exponenciais = np.exp(probabilidades - probabilidades.max())

        probabilidades = exponenciais / exponenciais.sum()

    return probabilidades.astype(np.float32)


def nivel_confianca(confianca: float) -> str:
    if confianca >= 0.80:
        return "alta"

    if confianca >= 0.60:
        return "media"

    return "baixa"


def classificar(
    modelo: Any,
    classes: list[str],
    caminho_imagem: str | Path,
    *,
    quantidade_principais: int = 3,
) -> ResultadoClassificacao:
    entrada = carregar_matriz_imagem(caminho_imagem, tamanho_entrada(modelo))

    inicio = time.perf_counter()

    valores_brutos = modelo.predict(entrada, verbose=0)[0]

    tempo_inferencia_ms = int((time.perf_counter() - inicio) * 1000)

    probabilidades = normalizar_probabilidades(valores_brutos)

    if len(probabilidades) != len(classes):
        raise ValueError(
            f"O modelo possui {len(probabilidades)} saídas, mas há {len(classes)} classes."
        )

    ordem = np.argsort(probabilidades)[::-1]

    indice_principal = int(ordem[0])

    confianca = float(probabilidades[indice_principal])

    classe = classes[indice_principal]

    principais = [
        {
            "classe": classes[int(indice)],
            "probabilidade": float(probabilidades[int(indice)]),
            "percentual": float(probabilidades[int(indice)] * 100),
        }
        for indice in ordem[:max(1, min(quantidade_principais, len(classes)))]
    ]

    return ResultadoClassificacao(
        caminho_imagem=str(Path(caminho_imagem).resolve()),
        classe_prevista=classe,
        confianca=confianca,
        confianca_percentual=confianca * 100,
        nivel_confianca=nivel_confianca(confianca),
        tempo_inferencia_ms=tempo_inferencia_ms,
        principais_predicoes=principais,
        todas_probabilidades={
            classes[indice]: float(probabilidades[indice])
            for indice in range(len(classes))
        },
    )


def salvar_classificacao(resultado: ResultadoClassificacao, caminho: str | Path) -> None:
    Path(caminho).write_text(
        json.dumps(asdict(resultado), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
