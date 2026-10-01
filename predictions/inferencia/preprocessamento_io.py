"""Operações de entrada, saída e apresentação de imagens."""

from pathlib import Path

import cv2
import numpy as np


def ler_imagem(caminho: Path) -> np.ndarray | None:

    try:
        dados = np.fromfile(caminho, dtype=np.uint8)
    except OSError:
        return None

    return cv2.imdecode(dados, cv2.IMREAD_COLOR)


def salvar_imagem(caminho: Path, imagem: np.ndarray) -> None:

    caminho.parent.mkdir(parents=True, exist_ok=True)

    sucesso, dados = cv2.imencode(caminho.suffix.lower(), imagem)

    if not sucesso:
        raise RuntimeError(f"Falha ao codificar {caminho}")

    dados.tofile(caminho)


def painel_com_rotulo(
    imagem: np.ndarray,
    rotulo: str,
    largura: int = 420,
    altura: int = 315,
) -> np.ndarray:

    if imagem.ndim == 2:
        imagem = cv2.cvtColor(imagem, cv2.COLOR_GRAY2BGR)

    escala = min(largura / imagem.shape[1], altura / imagem.shape[0])

    tamanho = (
        max(1, round(imagem.shape[1] * escala)),
        max(1, round(imagem.shape[0] * escala)),
    )

    redimensionada = cv2.resize(imagem, tamanho, interpolation=cv2.INTER_AREA)

    painel = np.full((altura + 38, largura, 3), 245, dtype=np.uint8)

    x = (largura - redimensionada.shape[1]) // 2

    y = (altura - redimensionada.shape[0]) // 2

    painel[y : y + redimensionada.shape[0], x : x + redimensionada.shape[1]] = redimensionada

    cv2.putText(
        painel,
        rotulo,
        (8, altura + 26),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
        (20, 20, 20),
        1,
        cv2.LINE_AA,
    )

    return painel
