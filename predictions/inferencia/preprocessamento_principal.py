"""Pré-processamento de produção consolidado a partir da v016 aprovada.

Este módulo não depende das implementações experimentais em
``mobilesam_versions``. As versões históricas continuam imutáveis para reprodução
dos experimentos.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np

from .preprocessamento import (
    AvaliacaoMascara,
    COR_FUNDO,
    EXTENSOES_SUPORTADAS,
    GeometriaGuia,
    PreditorSAM,
    avaliar_mascara,
    calcular_guias_busca,
    desenhar_guias,
    escolher_candidata,
)
from .preprocessamento_io import ler_imagem, metricas, painel_com_rotulo, salvar_imagem


VERSAO = "v016_limite_complexidade"

TAMANHO_MODELO = 224

MARGEM_VISUAL = 0.08

REMOCAO_MAXIMA = 0.25

LIMITE_FOCO = 200.0

LIMITE_MENOR_LADO = 400

LIMITE_PIXELS_CLAROS_PCT = 10.0


@dataclass(frozen=True)
class ResultadoSelecao:
    indice: int | None

    avaliacoes: list[AvaliacaoMascara]

    metricas: dict[str, Any]

    interromper_busca: bool = False


@dataclass(frozen=True)
class QualidadeCaptura:
    status: str

    avisos: list[str]

    foco_laplaciano: float

    menor_lado_px: int

    pixels_claros_pct: float


@dataclass
class ResultadoProcessamento:
    versao_preprocessamento: str

    status: str

    arquivo_entrada: str

    arquivo_saida: str

    arquivo_visual: str

    arquivo_modelo: str

    arquivo_guia: str

    pasta_execucao: str

    motivos: list[str]

    confianca: float | None

    candidato_escolhido: int | None

    regiao_escolhida: str | None

    guia: dict[str, int]

    tempo_codificacao_s: float

    tempo_prompt_s: float

    dispositivo: str

    avaliacoes_candidatas: list[dict[str, Any]]

    tentativas: list[dict[str, Any]]

    metricas_qualidade: dict[str, Any]

    qualidade_captura: str = "nao_avaliada"

    avisos_qualidade: list[str] = field(default_factory=list)


TransformadorMascara = Callable[
    [np.ndarray, GeometriaGuia], tuple[np.ndarray, dict[str, Any]]
]

CompositorVisual = Callable[[np.ndarray, np.ndarray], np.ndarray]

SeletorCandidata = Callable[
    [np.ndarray, np.ndarray, np.ndarray, GeometriaGuia], ResultadoSelecao
]


def _componentes(mascara: np.ndarray) -> int:
    quantidade, _, estatisticas, _ = cv2.connectedComponentsWithStats(
        mascara.astype(np.uint8), connectivity=8
    )

    limite = mascara.size * 0.002

    return sum(
        int(estatisticas[indice, cv2.CC_STAT_AREA]) >= limite
        for indice in range(1, quantidade)
    )


def metricas_mascara(imagem: np.ndarray, mascara: np.ndarray) -> dict[str, Any]:
    binaria = mascara.astype(np.uint8)

    cinza = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)

    borda_interna = binaria - cv2.erode(
        binaria, np.ones((3, 3), np.uint8), iterations=1
    )

    pixels_borda = cinza[borda_interna > 0]

    return {
        "proporcao_area_imagem": round(float(binaria.mean()), 6),
        "componentes_relevantes": _componentes(binaria),
        "pixels_borda_escuros_pct": round(
            float(np.mean(pixels_borda <= 30) * 100) if pixels_borda.size else 0.0,
            3,
        ),
    }


def limpar_mascara(
    mascara: np.ndarray, guia: GeometriaGuia
) -> tuple[np.ndarray, dict[str, Any]]:
    """Mantem o componente ligado ao prompt sem alterar sua geometria."""

    original = mascara.astype(np.uint8)

    total_original = int(original.sum())

    if total_original == 0:
        return mascara.astype(bool), {
            "limpeza_aplicada": False,
            "area_removida_pct": 0.0,
            "motivo_limpeza": "mascara_vazia",
        }

    quantidade, rotulos, _, _ = cv2.connectedComponentsWithStats(
        original, connectivity=8
    )

    rotulo_ponto = int(rotulos[guia.ponto_y, guia.ponto_x]) if quantidade > 1 else 0

    if rotulo_ponto == 0:
        return mascara.astype(bool), {
            "limpeza_aplicada": False,
            "area_removida_pct": 0.0,
            "motivo_limpeza": "componente_do_prompt_nao_encontrado",
        }

    limpa = (rotulos == rotulo_ponto).astype(np.uint8)

    removida = max(0.0, 1.0 - float(limpa.sum()) / total_original)

    if removida > REMOCAO_MAXIMA:
        return mascara.astype(bool), {
            "limpeza_aplicada": False,
            "area_removida_pct": round(removida * 100, 3),
            "motivo_limpeza": "remocao_excessiva_revertida",
        }

    return limpa.astype(bool), {
        "limpeza_aplicada": True,
        "area_removida_pct": round(removida * 100, 3),
        "metodo_limpeza": "componente_original_do_prompt",
    }


def compor_visual_nativo(
    imagem: np.ndarray,
    mascara: np.ndarray,
    *,
    suavizar_borda: bool = True,
    margem: float = MARGEM_VISUAL,
    recuar_borda: bool = False,
) -> np.ndarray:
    binaria = mascara.astype(np.uint8)

    pontos = cv2.findNonZero(binaria)

    if pontos is None:
        raise ValueError("Não é possível compor uma máscara vazia.")

    x, y, largura, altura = cv2.boundingRect(pontos)

    margem_px = max(4, round(max(largura, altura) * margem))

    lado = max(largura, altura) + 2 * margem_px

    centro_x, centro_y = x + largura / 2, y + altura / 2

    origem_x, origem_y = round(centro_x - lado / 2), round(centro_y - lado / 2)

    recorte_imagem = np.full((lado, lado, 3), COR_FUNDO, dtype=np.uint8)

    recorte_mascara = np.zeros((lado, lado), dtype=np.uint8)

    altura_imagem, largura_imagem = imagem.shape[:2]

    fonte_x1, fonte_y1 = max(0, origem_x), max(0, origem_y)

    fonte_x2, fonte_y2 = min(largura_imagem, origem_x + lado), min(
        altura_imagem, origem_y + lado
    )

    destino_x1, destino_y1 = fonte_x1 - origem_x, fonte_y1 - origem_y

    destino_x2 = destino_x1 + fonte_x2 - fonte_x1

    destino_y2 = destino_y1 + fonte_y2 - fonte_y1

    recorte_imagem[destino_y1:destino_y2, destino_x1:destino_x2] = imagem[
        fonte_y1:fonte_y2, fonte_x1:fonte_x2
    ]

    recorte_mascara[destino_y1:destino_y2, destino_x1:destino_x2] = binaria[
        fonte_y1:fonte_y2, fonte_x1:fonte_x2
    ]

    if suavizar_borda:
        interior = recorte_mascara

        if recuar_borda:
            interior = cv2.erode(
                recorte_mascara, np.ones((3, 3), np.uint8), iterations=1
            )

        alfa = cv2.GaussianBlur(interior.astype(np.float32), (0, 0), sigmaX=0.8)

        alfa = np.clip(alfa, 0.0, 1.0)[..., None]
    else:
        alfa = recorte_mascara.astype(np.float32)[..., None]

    fundo = np.full_like(recorte_imagem, COR_FUNDO)

    return np.rint(recorte_imagem * alfa + fundo * (1.0 - alfa)).astype(np.uint8)


def compor_visual_fallback(imagem: np.ndarray, guia: GeometriaGuia) -> np.ndarray:
    return imagem[guia.y : guia.y + guia.lado, guia.x : guia.x + guia.lado].copy()


def gerar_imagem_modelo(
    visual: np.ndarray, tamanho: int = TAMANHO_MODELO
) -> np.ndarray:
    interpolacao = (
        cv2.INTER_AREA if max(visual.shape[:2]) >= tamanho else cv2.INTER_CUBIC
    )

    return cv2.resize(visual, (tamanho, tamanho), interpolation=interpolacao)


def avaliar_qualidade_captura(
    imagem: np.ndarray, regiao_escolhida: str | None
) -> QualidadeCaptura:
    foco, _, _, pixels_claros = metricas(imagem)

    avisos: list[str] = []

    if foco < LIMITE_FOCO:
        avisos.append("baixa_nitidez")

    menor_lado = min(imagem.shape[:2])

    if menor_lado < LIMITE_MENOR_LADO:
        avisos.append("baixa_resolucao")

    if pixels_claros > LIMITE_PIXELS_CLAROS_PCT:
        avisos.append("superexposicao_parcial")

    if regiao_escolhida not in (None, "centro"):
        avisos.append("folha_fora_do_centro")

    return QualidadeCaptura(
        status="atencao" if avisos else "adequada",
        avisos=avisos,
        foco_laplaciano=round(foco, 3),
        menor_lado_px=int(menor_lado),
        pixels_claros_pct=round(pixels_claros, 3),
    )


def _iou(mascara_a: np.ndarray, mascara_b: np.ndarray) -> float:
    intersecao = int(np.logical_and(mascara_a, mascara_b).sum())

    uniao = int(np.logical_or(mascara_a, mascara_b).sum())

    return intersecao / uniao if uniao else 0.0


def _fracao_vegetacao(imagem: np.ndarray, mascara: np.ndarray) -> float:
    pixels = imagem[mascara].astype(np.int16)

    if not len(pixels):
        return 0.0

    azul, verde, vermelho = pixels[:, 0], pixels[:, 1], pixels[:, 2]

    return float(np.mean(2 * verde - vermelho - azul > 10))


def _guia_de_argumentos(argumentos: dict[str, Any]) -> GeometriaGuia:
    caixa = np.asarray(argumentos["box"], dtype=np.float32).reshape(-1)

    pontos = np.asarray(argumentos["point_coords"], dtype=np.float32).reshape(-1, 2)

    x1, y1, x2, y2 = (round(float(item)) for item in caixa)

    return GeometriaGuia(
        x=x1,
        y=y1,
        lado=max(x2 - x1 + 1, y2 - y1 + 1),
        ponto_x=round(float(pontos[0, 0])),
        ponto_y=round(float(pontos[0, 1])),
    )


def _ponto_interno(mascara: np.ndarray) -> tuple[int, int]:
    distancia = cv2.distanceTransform(mascara.astype(np.uint8), cv2.DIST_L2, 5)

    _, _, _, ponto = cv2.minMaxLoc(distancia)

    return int(ponto[0]), int(ponto[1])


def detectar_centros(
    mascara: np.ndarray, guia: GeometriaGuia
) -> tuple[np.ndarray | None, list[np.ndarray], list[tuple[int, int]], dict[str, Any]]:
    binaria = mascara.astype(np.uint8)

    area_total = int(np.count_nonzero(binaria))

    distancia = cv2.distanceTransform(binaria, cv2.DIST_L2, 5)

    sigma = max(1.0, guia.lado * 0.012)

    suave = cv2.GaussianBlur(distancia, (0, 0), sigmaX=sigma)

    diametro = max(15, round(guia.lado * 0.18))

    if diametro % 2 == 0:
        diametro += 1

    nucleo = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (diametro, diametro))

    dilatada = cv2.dilate(suave, nucleo)

    maximos = np.logical_and(suave >= dilatada - 1e-4, suave >= guia.lado * 0.025)

    quantidade, rotulos = cv2.connectedComponents(
        maximos.astype(np.uint8), connectivity=8
    )

    centros: list[tuple[int, int, float]] = []

    for indice in range(1, quantidade):
        ys, xs = np.nonzero(rotulos == indice)

        if not len(xs):
            continue

        valores = suave[ys, xs]

        melhor = int(np.argmax(valores))

        centros.append((int(xs[melhor]), int(ys[melhor]), float(valores[melhor])))

    centros.sort(key=lambda item: item[2], reverse=True)

    espacados: list[tuple[int, int, float]] = []

    distancia_minima = guia.lado * 0.14

    for centro in centros:
        if all(
            np.hypot(centro[0] - outro[0], centro[1] - outro[1])
            >= distancia_minima
            for outro in espacados
        ):
            espacados.append(centro)

        if len(espacados) == 4:
            break

    if len(espacados) < 2:
        return None, [], [], {
            "centros_detectados": len(espacados),
            "diametro_maximos_px": diametro,
        }

    ys, xs = np.nonzero(binaria)

    distancias = np.stack(
        [(xs - x) ** 2 + (ys - y) ** 2 for x, y, _ in espacados], axis=1
    )

    donos = np.argmin(distancias, axis=1)

    lobos: list[np.ndarray] = []

    centros_validos: list[tuple[int, int]] = []

    limite = max(round(area_total * 0.12), round(guia.lado * guia.lado * 0.012))

    for indice, (x, y, _) in enumerate(espacados):
        selecao = donos == indice

        if int(np.count_nonzero(selecao)) < limite:
            continue

        lobo = np.zeros_like(binaria, dtype=bool)

        lobo[ys[selecao], xs[selecao]] = True

        lobos.append(lobo)

        centros_validos.append((x, y))

    if len(lobos) < 2:
        return None, [], [], {
            "centros_detectados": len(lobos),
            "diametro_maximos_px": diametro,
        }

    distancias_ponto = [
        (x - guia.ponto_x) ** 2 + (y - guia.ponto_y) ** 2
        for x, y in centros_validos
    ]

    indice_central = int(np.argmin(distancias_ponto))

    central = lobos[indice_central]

    secundarios = [
        lobo for indice, lobo in enumerate(lobos) if indice != indice_central
    ]

    negativos = [
        centro
        for indice, centro in enumerate(centros_validos)
        if indice != indice_central
    ][:3]

    return central, secundarios, negativos, {
        "centros_detectados": len(lobos),
        "centros_secundarios": len(secundarios),
        "pontos_negativos": [[x, y] for x, y in negativos],
        "diametro_maximos_px": diametro,
    }


def _negativos_cantos(mascara: np.ndarray, caixa: np.ndarray) -> list[list[float]]:
    x1, y1, x2, y2 = caixa.reshape(-1)

    margem_x = max(2.0, (x2 - x1) * 0.06)

    margem_y = max(2.0, (y2 - y1) * 0.06)

    cantos = (
        (x1 + margem_x, y1 + margem_y),
        (x2 - margem_x, y1 + margem_y),
        (x1 + margem_x, y2 - margem_y),
        (x2 - margem_x, y2 - margem_y),
    )

    negativos: list[list[float]] = []

    for x, y in cantos:
        px = min(max(0, round(float(x))), mascara.shape[1] - 1)

        py = min(max(0, round(float(y))), mascara.shape[0] - 1)

        if not bool(mascara[py, px]):
            negativos.append([float(x), float(y)])

    return negativos


class PreditorPrincipal:
    """Gera as propostas finais da v016 sem herdar versões experimentais."""

    def __init__(self, preditor: PreditorSAM) -> None:
        self.preditor = preditor

        self.origens: list[str] = []

        self.quantidade_originais = 0

        self.indice_base: int | None = None

        self.lobo_central: np.ndarray | None = None

        self.lobos_secundarios: list[np.ndarray] = []

        self.metricas_lobos: dict[str, Any] = {}

    def set_image(self, imagem: np.ndarray) -> None:
        self.preditor.set_image(imagem)

    def predict(self, **argumentos: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        mascaras, confiancas, logitos = self.preditor.predict(**argumentos)

        mascaras = np.asarray(mascaras, dtype=bool)

        confiancas = np.asarray(confiancas, dtype=np.float32)

        logitos = np.asarray(logitos)

        self.quantidade_originais = len(mascaras)

        self.origens = [
            f"sam_original_{indice + 1}" for indice in range(len(mascaras))
        ]

        self.lobo_central = None

        self.lobos_secundarios = []

        self.metricas_lobos = {}

        guia = _guia_de_argumentos(argumentos)

        self.indice_base, avaliacoes = escolher_candidata(mascaras, confiancas, guia)

        if self.indice_base is None:
            return mascaras, confiancas, logitos

        todas = list(mascaras)

        todas_pontuacoes = [float(item) for item in confiancas]

        todos_logitos = list(logitos)

        base = mascaras[self.indice_base]

        avaliacao_base = avaliacoes[self.indice_base]

        positivos = np.asarray(argumentos["point_coords"], dtype=np.float32).reshape(-1, 2)

        if avaliacao_base.componentes > 1:
            caixa = np.asarray(argumentos["box"], dtype=np.float32)

            for indice, (mascara, logito) in enumerate(zip(mascaras, logitos)):
                negativos = _negativos_cantos(mascara, caixa)

                pontos = positivos

                rotulos = np.ones(len(positivos), dtype=np.int32)

                if negativos:
                    pontos = np.vstack(
                        (positivos, np.asarray(negativos, dtype=np.float32))
                    )

                    rotulos = np.concatenate(
                        (rotulos, np.zeros(len(negativos), dtype=np.int32))
                    )

                novas, pontuacoes, novos_logitos = self.preditor.predict(
                    point_coords=pontos,
                    point_labels=rotulos,
                    box=argumentos["box"],
                    mask_input=np.asarray(logito, dtype=np.float32)[None, ...],
                    multimask_output=False,
                )

                todas.append(novas[0].astype(bool))

                todas_pontuacoes.append(float(pontuacoes[0]))

                todos_logitos.append(novos_logitos[0])

                self.origens.append(f"recuperacao_logit_{indice + 1}")
        else:
            central, secundarios, negativos, metricas_lobos = detectar_centros(
                base, guia
            )

            self.lobo_central = central

            self.lobos_secundarios = secundarios

            self.metricas_lobos = metricas_lobos

            if central is not None and negativos:
                negativos_array = np.asarray(negativos, dtype=np.float32)

                pontos = np.vstack((positivos, negativos_array))

                rotulos = np.concatenate(
                    (
                        np.ones(len(positivos), dtype=np.int32),
                        np.zeros(len(negativos_array), dtype=np.int32),
                    )
                )

                exploratorias, pontuacoes, novos_logitos = self.preditor.predict(
                    point_coords=pontos,
                    point_labels=rotulos,
                    box=argumentos["box"],
                    multimask_output=True,
                )

                for indice, mascara in enumerate(exploratorias):
                    todas.append(mascara.astype(bool))

                    todas_pontuacoes.append(float(pontuacoes[indice]))

                    todos_logitos.append(novos_logitos[indice])

                    self.origens.append(f"exploratoria_lobos_{indice + 1}")

                original = positivos[0]

                ancora = np.asarray(_ponto_interno(central), dtype=np.float32)

                prompts_positivos = (
                    np.asarray([original, ancora], dtype=np.float32),
                    np.asarray([ancora], dtype=np.float32),
                    np.asarray([0.25 * original + 0.75 * ancora], dtype=np.float32),
                    np.asarray([0.50 * original + 0.50 * ancora], dtype=np.float32),
                )

                for indice, positivos_ancora in enumerate(prompts_positivos, start=1):
                    pontos = np.vstack((positivos_ancora, negativos_array))

                    rotulos = np.concatenate(
                        (
                            np.ones(len(positivos_ancora), dtype=np.int32),
                            np.zeros(len(negativos_array), dtype=np.int32),
                        )
                    )

                    novas, pontuacoes, novos_logitos = self.preditor.predict(
                        point_coords=pontos,
                        point_labels=rotulos,
                        box=argumentos["box"],
                        multimask_output=False,
                    )

                    todas.append(novas[0].astype(bool))

                    todas_pontuacoes.append(float(pontuacoes[0]))

                    todos_logitos.append(novos_logitos[0])

                    self.origens.append(f"separacao_lobos_ancora_{indice}")

                self.metricas_lobos["ponto_ancora_interna"] = [
                    round(float(ancora[0])),
                    round(float(ancora[1])),
                ]

        centros = int(self.metricas_lobos.get("centros_detectados", 0))

        if centros > 3:
            manter = [
                indice
                for indice, origem in enumerate(self.origens)
                if origem.startswith("sam_original_")
                or origem.startswith("recuperacao_logit_")
            ]

            self.origens = [self.origens[indice] for indice in manter]

            self.metricas_lobos[
                "separacao_bloqueada"
            ] = "complexidade_maior_que_tres_centros"

            todas = [todas[indice] for indice in manter]

            todas_pontuacoes = [todas_pontuacoes[indice] for indice in manter]

            todos_logitos = [todos_logitos[indice] for indice in manter]

        return (
            np.asarray(todas, dtype=bool),
            np.asarray(todas_pontuacoes, dtype=np.float32),
            np.asarray(todos_logitos),
        )


class SeletorPrincipal:
    def __init__(self, preditor: PreditorPrincipal) -> None:
        self.preditor = preditor

    def __call__(
        self,
        imagem: np.ndarray,
        mascaras: np.ndarray,
        confiancas: np.ndarray,
        guia: GeometriaGuia,
    ) -> ResultadoSelecao:
        quantidade = self.preditor.quantidade_originais

        indice_base, avaliacoes_base = escolher_candidata(
            mascaras[:quantidade], confiancas[:quantidade], guia
        )

        avaliacoes = [
            avaliar_mascara(mascara, float(confiancas[indice]), guia, indice)
            for indice, mascara in enumerate(mascaras)
        ]

        if indice_base is None:
            return ResultadoSelecao(
                None,
                avaliacoes,
                {
                    "metodo_selecao": "v012_sem_base",
                    "candidatas_avaliadas": len(mascaras),
                },
            )

        base = mascaras[indice_base]

        area_base = int(np.count_nonzero(base))

        confianca_base = float(confiancas[indice_base])

        vegetacao_base = _fracao_vegetacao(imagem, base)

        componentes_base = avaliacoes_base[indice_base].componentes

        detalhes: list[dict[str, Any]] = []

        aceitas: list[dict[str, Any]] = []

        indices_separacao = [
            indice
            for indice, origem in enumerate(self.preditor.origens)
            if origem.startswith("separacao_lobos_")
        ]

        for indice, (mascara, confianca, avaliacao) in enumerate(
            zip(mascaras, confiancas, avaliacoes)
        ):
            origem = self.preditor.origens[indice]

            area = int(np.count_nonzero(mascara))

            razao_area = area / area_base if area_base else 0.0

            toca_foto = bool(
                np.any(mascara[0, :])
                or np.any(mascara[-1, :])
                or np.any(mascara[:, 0])
                or np.any(mascara[:, -1])
            )

            precisao_base = (
                float(np.logical_and(mascara, base).sum()) / area if area else 0.0
            )

            recupera = (
                origem.startswith("recuperacao_logit_")
                and componentes_base > 1
                and float(confianca) >= confianca_base + 0.04
                and 1.10 <= razao_area <= 1.60
                and _fracao_vegetacao(imagem, mascara) >= vegetacao_base - 0.20
                and avaliacao.contem_ponto_central
                and not toca_foto
            )

            concordancias = 0

            cobertura_central = 0.0

            cobertura_secundarios = 1.0

            if origem.startswith("separacao_lobos_"):
                concordancias = sum(
                    _iou(mascara, mascaras[outro]) >= 0.82
                    for outro in indices_separacao
                    if outro != indice
                )

                central = self.preditor.lobo_central

                if central is not None and np.any(central):
                    cobertura_central = float(np.logical_and(mascara, central).sum()) / float(
                        np.count_nonzero(central)
                    )

                secundarios = self.preditor.lobos_secundarios

                area_secundaria = sum(np.count_nonzero(item) for item in secundarios)

                if area_secundaria:
                    cobertura_secundarios = sum(
                        np.logical_and(mascara, item).sum() for item in secundarios
                    ) / float(area_secundaria)

            separa = (
                origem.startswith("separacao_lobos_")
                and 0.30 <= razao_area <= 0.85
                and float(confianca) >= confianca_base - 0.25
                and precisao_base >= 0.96
                and cobertura_central >= 0.90
                and cobertura_secundarios <= 0.35
                and concordancias >= 2
                and avaliacao.contem_ponto_central
                and avaliacao.componentes <= 2
                and not toca_foto
            )

            motivo = (
                "recuperacao_area"
                if recupera
                else "separacao_estavel" if separa else None
            )

            item = {
                "indice": indice,
                "origem": origem,
                "confianca_sam": round(float(confianca), 6),
                "razao_area": round(razao_area, 6),
                "precisao_relativa_base": round(precisao_base, 6),
                "recall_lobo_central": round(cobertura_central, 6),
                "recall_lobos_secundarios": round(float(cobertura_secundarios), 6),
                "concordancias": concordancias,
                "aceita": motivo is not None,
                "motivo": motivo,
            }

            detalhes.append(item)

            if motivo is not None:
                aceitas.append(item)

        if aceitas:
            aceitas.sort(
                key=lambda item: (
                    item["motivo"] == "recuperacao_area",
                    item["concordancias"],
                    item["confianca_sam"],
                ),
                reverse=True,
            )

            escolhida = aceitas[0]

            indice = int(escolhida["indice"])

            decisao = str(escolhida["motivo"])
        else:
            indice = indice_base

            decisao = "manter_v008"

        return ResultadoSelecao(
            indice,
            avaliacoes,
            {
                "metodo_selecao": "separacao_estavel",
                "origem_candidata": self.preditor.origens[indice],
                "decisao_refino": decisao,
                "candidatas_avaliadas": len(mascaras),
                "metricas_lobos": self.preditor.metricas_lobos,
                "metricas_candidatas": detalhes,
                "selecao_ambigua": False,
            },
        )


def _salvar_diagnosticos(
    pasta: Path,
    imagem: np.ndarray,
    guias: list[GeometriaGuia],
    guia: GeometriaGuia,
    mascaras: np.ndarray,
    confiancas: np.ndarray,
    escolhida: int | None,
    mascara_final: np.ndarray | None,
    visual: np.ndarray,
    modelo: np.ndarray,
    status: str,
) -> None:
    salvar_imagem(
        pasta / "01_original_com_guias.jpg",
        desenhar_guias(imagem, guias, guia.posicao),
    )

    salvar_imagem(
        pasta / "02_recorte_guia.jpg",
        imagem[guia.y : guia.y + guia.lado, guia.x : guia.x + guia.lado],
    )

    for posicao, indice in enumerate(np.argsort(confiancas)[::-1], start=1):
        salvar_imagem(
            pasta / f"03_candidata_{posicao}_mascara.png",
            mascaras[int(indice)].astype(np.uint8) * 255,
        )

    if escolhida is not None:
        salvar_imagem(
            pasta / "04_mascara_sam.png", mascaras[escolhida].astype(np.uint8) * 255
        )

    if mascara_final is not None:
        salvar_imagem(
            pasta / "05_mascara_final.png", mascara_final.astype(np.uint8) * 255
        )

    painel = np.hstack(
        (
            painel_com_rotulo(
                desenhar_guias(imagem, guias, guia.posicao), "Original + guias"
            ),
        painel_com_rotulo(visual, f"Visual sem perdas - {status}"),
            painel_com_rotulo(modelo, "Entrada Modelo V5 - 224"),
        )
    )

    salvar_imagem(pasta / "06_painel.jpg", painel)


def _processar(
    preditor: PreditorPrincipal,
    caminho_imagem: Path,
    pasta_execucao: Path,
    *,
    seletor: SeletorPrincipal,
    diagnosticos: bool,
    dispositivo: str,
) -> ResultadoProcessamento:
    caminho_imagem = caminho_imagem.resolve()

    if caminho_imagem.suffix.lower() not in EXTENSOES_SUPORTADAS:
        raise ValueError("Formato não suportado. Use JPG, JPEG ou PNG.")

    imagem = ler_imagem(caminho_imagem)

    if imagem is None:
        raise RuntimeError(f"Não foi possível ler a imagem: {caminho_imagem}")

    pasta_execucao.mkdir(parents=True, exist_ok=False)

    altura, largura = imagem.shape[:2]

    guias = calcular_guias_busca(largura, altura)

    guia_central = guias[0]

    inicio = time.perf_counter()

    preditor.set_image(cv2.cvtColor(imagem, cv2.COLOR_BGR2RGB))

    tempo_codificacao = time.perf_counter() - inicio

    tempo_prompt = 0.0

    escolhida: int | None = None

    guia_escolhida: GeometriaGuia | None = None

    mascaras: np.ndarray | None = None

    confiancas: np.ndarray | None = None

    avaliacoes: list[AvaliacaoMascara] = []

    tentativas: list[dict[str, Any]] = []

    metricas_selecao: dict[str, Any] = {}

    for guia_tentativa in guias:
        inicio = time.perf_counter()

        mascaras_tentativa, confiancas_tentativa, _ = preditor.predict(
            point_coords=np.array(
                [[guia_tentativa.ponto_x, guia_tentativa.ponto_y]], dtype=np.float32
            ),
            point_labels=np.array([1], dtype=np.int32),
            box=np.array(guia_tentativa.caixa, dtype=np.float32),
            multimask_output=True,
        )

        duracao = time.perf_counter() - inicio

        tempo_prompt += duracao

        selecao = seletor(
            imagem, mascaras_tentativa, confiancas_tentativa, guia_tentativa
        )

        tentativas.append(
            {
                "posicao": guia_tentativa.posicao,
                "tempo_prompt_s": round(duracao, 4),
                "candidato_valido": selecao.indice,
                "guia": asdict(guia_tentativa),
                "avaliacoes": [asdict(item) for item in selecao.avaliacoes],
                "metricas_selecao": selecao.metricas,
            }
        )

        mascaras, confiancas, avaliacoes = (
            mascaras_tentativa,
            confiancas_tentativa,
            selecao.avaliacoes,
        )

        metricas_selecao = selecao.metricas

        if selecao.indice is None and selecao.interromper_busca:
            break

        if selecao.indice is not None:
            escolhida = selecao.indice

            guia_escolhida = guia_tentativa

            break

    assert mascaras is not None and confiancas is not None

    mascara_final: np.ndarray | None = None

    if escolhida is None:
        status = "fallback_roi"

        guia_resultado = guia_central

        visual = compor_visual_fallback(imagem, guia_central)

        motivos = sorted({motivo for item in avaliacoes for motivo in item.motivos})

        confianca = None

        metricas_qualidade = {
            "limpeza_aplicada": False,
            "area_removida_pct": 0.0,
            "fallback": True,
        } | metricas_selecao
    else:
        status = "segmentada"

        assert guia_escolhida is not None

        guia_resultado = guia_escolhida

        mascara_final, dados_limpeza = limpar_mascara(
            mascaras[escolhida].astype(bool), guia_escolhida
        )

        visual = compor_visual_nativo(imagem, mascara_final)

        motivos = []

        confianca = float(confiancas[escolhida])

        metricas_qualidade = (
            metricas_mascara(imagem, mascara_final)
            | dados_limpeza
            | metricas_selecao
            | {"fallback": False}
        )

    modelo = gerar_imagem_modelo(visual)

    cinza_visual = cv2.cvtColor(visual, cv2.COLOR_BGR2GRAY)

    metricas_qualidade["foco_laplaciano_visual"] = round(
        float(cv2.Laplacian(cinza_visual, cv2.CV_64F).var()), 3
    )

    metricas_qualidade["resolucao_visual"] = [
        int(visual.shape[1]),
        int(visual.shape[0]),
    ]

    metricas_qualidade["resolucao_modelo"] = [
        int(modelo.shape[1]),
        int(modelo.shape[0]),
    ]

    arquivo_visual = pasta_execucao / "imagem_processada_visual.png"

    arquivo_modelo = pasta_execucao / "imagem_modelo.png"

    arquivo_guia = pasta_execucao / "imagem_com_guia.jpg"

    salvar_imagem(arquivo_visual, visual)

    salvar_imagem(arquivo_modelo, modelo)

    salvar_imagem(
        arquivo_guia,
        desenhar_guias(
            imagem,
            guias,
            guia_escolhida.posicao if guia_escolhida is not None else None,
        ),
    )

    if diagnosticos:
        _salvar_diagnosticos(
            pasta_execucao,
            imagem,
            guias,
            guia_resultado,
            mascaras,
            confiancas,
            escolhida,
            mascara_final,
            visual,
            modelo,
            status,
        )

    resultado = ResultadoProcessamento(
        versao_preprocessamento=VERSAO,
        status=status,
        arquivo_entrada=str(caminho_imagem),
        arquivo_saida=str(arquivo_modelo.resolve()),
        arquivo_visual=str(arquivo_visual.resolve()),
        arquivo_modelo=str(arquivo_modelo.resolve()),
        arquivo_guia=str(arquivo_guia.resolve()),
        pasta_execucao=str(pasta_execucao.resolve()),
        motivos=motivos,
        confianca=round(confianca, 6) if confianca is not None else None,
        candidato_escolhido=escolhida,
        regiao_escolhida=(
            guia_escolhida.posicao if guia_escolhida is not None else None
        ),
        guia={
            "x": guia_resultado.x,
            "y": guia_resultado.y,
            "lado": guia_resultado.lado,
            "ponto_x": guia_resultado.ponto_x,
            "ponto_y": guia_resultado.ponto_y,
        },
        tempo_codificacao_s=round(tempo_codificacao, 4),
        tempo_prompt_s=round(tempo_prompt, 4),
        dispositivo=dispositivo,
        avaliacoes_candidatas=[asdict(item) for item in avaliacoes],
        tentativas=tentativas,
        metricas_qualidade=metricas_qualidade,
    )

    qualidade = avaliar_qualidade_captura(imagem, resultado.regiao_escolhida)

    resultado.metricas_qualidade.update(
        {
            "foco_laplaciano_captura": qualidade.foco_laplaciano,
            "menor_lado_captura_px": qualidade.menor_lado_px,
            "pixels_claros_captura_pct": qualidade.pixels_claros_pct,
        }
    )

    resultado.qualidade_captura = qualidade.status

    resultado.avisos_qualidade = qualidade.avisos

    (pasta_execucao / "status.json").write_text(
        json.dumps(asdict(resultado), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return resultado


def processar_imagem(
    preditor: PreditorSAM,
    caminho_imagem: Path,
    pasta_execucao: Path,
    *,
    tamanho: int = 256,
    diagnosticos: bool = False,
    dispositivo: str = "desconhecido",
) -> ResultadoProcessamento:
    """Executa o pré-processamento principal equivalente à v016."""

    del tamanho

    principal = PreditorPrincipal(preditor)

    return _processar(
        principal,
        caminho_imagem,
        pasta_execucao,
        seletor=SeletorPrincipal(principal),
        diagnosticos=diagnosticos,
        dispositivo=dispositivo,
    )


__all__ = [
    "PreditorPrincipal",
    "QualidadeCaptura",
    "ResultadoProcessamento",
    "SeletorPrincipal",
    "VERSAO",
    "avaliar_qualidade_captura",
    "compor_visual_nativo",
    "detectar_centros",
    "gerar_imagem_modelo",
    "limpar_mascara",
    "processar_imagem",
]
