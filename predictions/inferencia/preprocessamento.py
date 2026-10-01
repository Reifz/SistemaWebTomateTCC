from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

import cv2
import numpy as np

from .preprocessamento_io import ler_imagem, painel_com_rotulo, salvar_imagem


PROPORCAO_GUIA = 0.55

PROPORCAO_DESLOCAMENTO = 0.20

TAMANHO_SAIDA = 256

OCUPACAO_FOLHA = 0.90

COR_FUNDO = 200

CONFIANCA_MINIMA = 0.85

AREA_MINIMA = 0.08

AREA_MAXIMA = 0.88

COMPONENTES_MAXIMOS = 5

EXTENSOES_SUPORTADAS = {".jpg", ".jpeg", ".png"}


class PreditorSAM(Protocol):
    def set_image(self, imagem: np.ndarray) -> None: ...

    def predict(self, **kwargs: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray]: ...


@dataclass(frozen=True)
class GeometriaGuia:
    x: int

    y: int

    lado: int

    ponto_x: int

    ponto_y: int

    posicao: str = "centro"

    @property
    def caixa(self) -> list[int]:
        return [self.x, self.y, self.x + self.lado - 1, self.y + self.lado - 1]


@dataclass(frozen=True)
class AvaliacaoMascara:
    indice_original: int

    confianca: float

    valida: bool

    motivos: list[str]

    proporcao_area: float

    componentes: int

    bordas_tocadas: int

    contem_ponto_central: bool


@dataclass
class ResultadoProcessamento:
    status: str

    arquivo_entrada: str

    arquivo_saida: str

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


def calcular_guia(largura: int, altura: int, proporcao: float = PROPORCAO_GUIA) -> GeometriaGuia:
    if largura <= 0 or altura <= 0:
        raise ValueError("A imagem deve possuir largura e altura positivas.")

    if not 0 < proporcao <= 1:
        raise ValueError("A proporção da guia deve estar no intervalo (0, 1].")

    lado = max(1, round(min(largura, altura) * proporcao))

    x = (largura - lado) // 2

    y = (altura - lado) // 2

    return GeometriaGuia(x=x, y=y, lado=lado, ponto_x=largura // 2, ponto_y=altura // 2)


def calcular_guias_busca(
    largura: int,
    altura: int,
    proporcao: float = PROPORCAO_GUIA,
    proporcao_deslocamento: float = PROPORCAO_DESLOCAMENTO,
) -> list[GeometriaGuia]:
    central = calcular_guia(largura, altura, proporcao)

    deslocamento = round(min(largura, altura) * proporcao_deslocamento)

    maximo_x = largura - central.lado

    def criar(posicao: str, x: int) -> GeometriaGuia:
        x_limitado = min(max(0, x), maximo_x)

        return GeometriaGuia(
            x=x_limitado,
            y=central.y,
            lado=central.lado,
            ponto_x=central.ponto_x if posicao == "centro" else x_limitado + central.lado // 2,
            ponto_y=central.ponto_y,
            posicao=posicao,
        )

    return [
        criar("centro", central.x),
        criar("direita", central.x + deslocamento),
        criar("esquerda", central.x - deslocamento),
    ]


def desenhar_guias(
    imagem: np.ndarray,
    guias: list[GeometriaGuia],
    posicao_escolhida: str | None,
) -> np.ndarray:
    visual = imagem.copy()

    espessura = max(2, round(min(imagem.shape[:2]) / 250))

    for guia in reversed(guias):
        escolhida = guia.posicao == (posicao_escolhida or "centro")

        cor = (0, 0, 255) if escolhida else (0, 180, 255)

        grossura = espessura + 1 if escolhida else espessura

        cv2.rectangle(
            visual,
            (guia.x, guia.y),
            (guia.x + guia.lado - 1, guia.y + guia.lado - 1),
            cor,
            grossura,
        )

        raio = max(3, grossura * 2)

        cv2.circle(visual, (guia.ponto_x, guia.ponto_y), raio, cor, -1)

        cv2.putText(
            visual,
            guia.posicao,
            (guia.x + 5, max(18, guia.y + 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            cor,
            max(1, grossura - 1),
            cv2.LINE_AA,
        )

    return visual


def desenhar_guia(imagem: np.ndarray, guia: GeometriaGuia) -> np.ndarray:
    """Compatibilidade para consumidores que desenham somente uma guia."""

    return desenhar_guias(imagem, [guia], guia.posicao)


def _metricas_mascara(mascara_roi: np.ndarray) -> tuple[float, int, int]:
    binaria = (mascara_roi > 0).astype(np.uint8)

    proporcao = float(binaria.mean())

    quantidade, _, estatisticas, _ = cv2.connectedComponentsWithStats(binaria, connectivity=8)

    componentes = sum(
        int(estatisticas[indice, cv2.CC_STAT_AREA]) >= mascara_roi.size * 0.002
        for indice in range(1, quantidade)
    )

    bordas = sum(
        bool(np.any(borda))
        for borda in (binaria[0, :], binaria[-1, :], binaria[:, 0], binaria[:, -1])
    )

    return proporcao, componentes, bordas


def avaliar_mascara(
    mascara_completa: np.ndarray,
    confianca: float,
    guia: GeometriaGuia,
    indice_original: int,
) -> AvaliacaoMascara:
    mascara_roi = mascara_completa[guia.y : guia.y + guia.lado, guia.x : guia.x + guia.lado]

    proporcao, componentes, bordas = _metricas_mascara(mascara_roi)

    contem_ponto = bool(mascara_completa[guia.ponto_y, guia.ponto_x])

    motivos: list[str] = []

    if not contem_ponto:
        motivos.append("mascara_nao_contem_ponto_central")

    if proporcao < AREA_MINIMA:
        motivos.append("mascara_muito_pequena")

    if proporcao > AREA_MAXIMA:
        motivos.append("mascara_ocupa_quase_toda_guia")

    if componentes > COMPONENTES_MAXIMOS:
        motivos.append("muitos_componentes")

    if bordas >= 2:
        motivos.append("folha_toca_duas_ou_mais_bordas_da_guia")

    if confianca < CONFIANCA_MINIMA:
        motivos.append("baixa_confianca_prevista")

    return AvaliacaoMascara(
        indice_original=indice_original,
        confianca=round(float(confianca), 6),
        valida=not motivos,
        motivos=motivos,
        proporcao_area=round(proporcao, 6),
        componentes=componentes,
        bordas_tocadas=bordas,
        contem_ponto_central=contem_ponto,
    )


def escolher_candidata(
    mascaras: np.ndarray, confiancas: np.ndarray, guia: GeometriaGuia
) -> tuple[int | None, list[AvaliacaoMascara]]:
    avaliacoes = [
        avaliar_mascara(mascaras[indice], float(confiancas[indice]), guia, indice)
        for indice in range(len(mascaras))
    ]

    validas = [avaliacao for avaliacao in avaliacoes if avaliacao.valida]

    escolhida = max(validas, key=lambda item: item.confianca).indice_original if validas else None

    return escolhida, avaliacoes


def compor_folha_centralizada(
    imagem: np.ndarray,
    mascara_completa: np.ndarray,
    tamanho: int = TAMANHO_SAIDA,
    ocupacao: float = OCUPACAO_FOLHA,
) -> np.ndarray:
    binaria = (mascara_completa > 0).astype(np.uint8)

    pontos = cv2.findNonZero(binaria)

    if pontos is None:
        raise ValueError("Não é possível compor uma máscara vazia.")

    x, y, largura, altura = cv2.boundingRect(pontos)

    recorte = imagem[y : y + altura, x : x + largura]

    mascara = binaria[y : y + altura, x : x + largura]

    limite = max(1, round(tamanho * ocupacao))

    escala = min(limite / largura, limite / altura)

    nova_largura = max(1, round(largura * escala))

    nova_altura = max(1, round(altura * escala))

    interpolacao = cv2.INTER_AREA if escala < 1 else cv2.INTER_CUBIC

    recorte_redimensionado = cv2.resize(
        recorte, (nova_largura, nova_altura), interpolation=interpolacao
    )

    mascara_redimensionada = cv2.resize(
        mascara, (nova_largura, nova_altura), interpolation=cv2.INTER_NEAREST
    )

    saida = np.full((tamanho, tamanho, 3), COR_FUNDO, dtype=np.uint8)

    inicio_x = (tamanho - nova_largura) // 2

    inicio_y = (tamanho - nova_altura) // 2

    destino = saida[inicio_y : inicio_y + nova_altura, inicio_x : inicio_x + nova_largura]

    destino[:] = np.where(
        mascara_redimensionada[..., None] > 0, recorte_redimensionado, destino
    )

    return saida


def compor_fallback_roi(
    imagem: np.ndarray, guia: GeometriaGuia, tamanho: int = TAMANHO_SAIDA
) -> np.ndarray:
    recorte = imagem[guia.y : guia.y + guia.lado, guia.x : guia.x + guia.lado]

    interpolacao = cv2.INTER_AREA if guia.lado >= tamanho else cv2.INTER_CUBIC

    return cv2.resize(recorte, (tamanho, tamanho), interpolation=interpolacao)


def _salvar_diagnosticos(
    pasta: Path,
    imagem: np.ndarray,
    guia: GeometriaGuia,
    mascaras: np.ndarray,
    confiancas: np.ndarray,
    escolhida: int | None,
    final: np.ndarray,
    status: str,
) -> None:
    visual_guia = desenhar_guia(imagem, guia)

    recorte = imagem[guia.y : guia.y + guia.lado, guia.x : guia.x + guia.lado]

    salvar_imagem(pasta / "01_original_com_guia.jpg", visual_guia)

    salvar_imagem(pasta / "02_recorte_central.jpg", recorte)

    ordem = np.argsort(confiancas)[::-1]

    for posicao, indice in enumerate(ordem, start=1):
        mascara = mascaras[int(indice)].astype(np.uint8) * 255

        salvar_imagem(pasta / f"03_candidata_{posicao}_mascara.png", mascara)

    if escolhida is not None:
        salvar_imagem(
            pasta / "04_mascara_escolhida.png",
            mascaras[escolhida].astype(np.uint8) * 255,
        )

    painel = np.hstack(
        (
            painel_com_rotulo(visual_guia, "Original + guia central"),
            painel_com_rotulo(recorte, "ROI central / fallback"),
            painel_com_rotulo(final, f"Saida 256 - {status}"),
        )
    )

    salvar_imagem(pasta / "05_painel.jpg", painel)


def processar_imagem(
    preditor: PreditorSAM,
    caminho_imagem: Path,
    pasta_execucao: Path,
    *,
    tamanho: int = TAMANHO_SAIDA,
    diagnosticos: bool = False,
    dispositivo: str = "desconhecido",
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

    imagem_rgb = cv2.cvtColor(imagem, cv2.COLOR_BGR2RGB)

    inicio = time.perf_counter()

    preditor.set_image(imagem_rgb)

    tempo_codificacao = time.perf_counter() - inicio

    tempo_prompt = 0.0

    escolhida: int | None = None

    guia_escolhida: GeometriaGuia | None = None

    mascaras: np.ndarray | None = None

    confiancas: np.ndarray | None = None

    avaliacoes: list[AvaliacaoMascara] = []

    tentativas: list[dict[str, Any]] = []

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

        escolhida_tentativa, avaliacoes_tentativa = escolher_candidata(
            mascaras_tentativa, confiancas_tentativa, guia_tentativa
        )

        tentativas.append(
            {
                "posicao": guia_tentativa.posicao,
                "tempo_prompt_s": round(duracao, 4),
                "candidato_valido": escolhida_tentativa,
                "guia": {
                    "x": guia_tentativa.x,
                    "y": guia_tentativa.y,
                    "lado": guia_tentativa.lado,
                    "ponto_x": guia_tentativa.ponto_x,
                    "ponto_y": guia_tentativa.ponto_y,
                },
                "avaliacoes": [asdict(item) for item in avaliacoes_tentativa],
            }
        )

        mascaras = mascaras_tentativa

        confiancas = confiancas_tentativa

        avaliacoes = avaliacoes_tentativa

        if escolhida_tentativa is not None:
            escolhida = escolhida_tentativa

            guia_escolhida = guia_tentativa

            break

    assert mascaras is not None and confiancas is not None

    if escolhida is None:
        status = "fallback_roi"

        final = compor_fallback_roi(imagem, guia_central, tamanho)

        motivos = sorted({motivo for item in avaliacoes for motivo in item.motivos})

        confianca = None

        guia_resultado = guia_central
    else:
        status = "segmentada"

        final = compor_folha_centralizada(imagem, mascaras[escolhida], tamanho)

        motivos = []

        confianca = float(confiancas[escolhida])

        assert guia_escolhida is not None

        guia_resultado = guia_escolhida

    arquivo_saida = pasta_execucao / "imagem_processada.jpg"

    arquivo_guia = pasta_execucao / "imagem_com_guia.jpg"

    salvar_imagem(arquivo_saida, final)

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
            guia_resultado,
            mascaras,
            confiancas,
            escolhida,
            final,
            status,
        )

    resultado = ResultadoProcessamento(
        status=status,
        arquivo_entrada=str(caminho_imagem),
        arquivo_saida=str(arquivo_saida.resolve()),
        arquivo_guia=str(arquivo_guia.resolve()),
        pasta_execucao=str(pasta_execucao.resolve()),
        motivos=motivos,
        confianca=round(confianca, 6) if confianca is not None else None,
        candidato_escolhido=escolhida,
        regiao_escolhida=guia_escolhida.posicao if guia_escolhida is not None else None,
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
    )

    (pasta_execucao / "status.json").write_text(
        json.dumps(asdict(resultado), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return resultado
