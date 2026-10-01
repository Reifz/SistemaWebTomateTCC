"""Orquestra o MobileSAM e o classificador MobileNetV2 V5."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4

import torch
from django.conf import settings
from mobile_sam import SamPredictor, sam_model_registry

from .classificador import (
    ResultadoClassificacao,
    carregar_classes,
    carregar_modelo,
    classificar,
    salvar_classificacao,
)
from .preprocessamento import ResultadoProcessamento, processar_imagem

NOME_MODELO = "MobileNetV2_Tomato_Modelo_B_v5"

HASHES_ARTEFATOS = {
    "mobile_sam.pt": "6DBB90523A35330FEDD7F1D3DFC66F995213D81B29A5CA8108DBCDD4E37D6C2F",
    "tomato_mobilenetv2_v5.keras": "B754BAA51329476147FE55E6CF2E794266FBB923EB250199BA13338857DC2758",
    "classes.txt": "D35DA33A0E74E1036C8D545B2B15A03D2162DE2364CEEFDA0CA253BE96CC975A",
}


class ErroArtefatoModelo(RuntimeError):
    """Indica ausência ou corrupção de um peso obrigatório."""


@dataclass
class RecursosInferencia:
    preditor_sam: SamPredictor

    modelo_predicao: Any

    classes: list[str]

    dispositivo: str


@dataclass
class ResultadoAnalise:
    id_execucao: str

    pasta_execucao: str

    arquivo_original: str

    arquivo_analisado: str

    preprocessamento: ResultadoProcessamento

    classificacao: ResultadoClassificacao

    aviso_fallback: bool

    tempo_mobilesam_ms: float


def pasta_modelos() -> Path:
    return Path(settings.MODELS_ROOT)


def verificar_modelos() -> None:
    for nome, hash_esperado in HASHES_ARTEFATOS.items():
        caminho = pasta_modelos() / nome

        if not caminho.is_file():
            raise ErroArtefatoModelo(f"Artefato obrigatório não encontrado: {caminho}")

        hash_atual = hashlib.sha256(caminho.read_bytes()).hexdigest().upper()

        if hash_atual != hash_esperado:
            raise ErroArtefatoModelo(f"O artefato {nome} foi alterado ou está corrompido.")


def carregar_preditor_sam(dispositivo: str = "auto") -> tuple[SamPredictor, str]:
    dispositivo_resolvido = "cuda" if dispositivo == "auto" and torch.cuda.is_available() else dispositivo

    if dispositivo_resolvido == "auto":
        dispositivo_resolvido = "cpu"

    caminho_pesos = pasta_modelos() / "mobile_sam.pt"

    modelo = sam_model_registry["vit_t"](checkpoint=str(caminho_pesos))

    modelo.to(device=dispositivo_resolvido)

    modelo.eval()

    return SamPredictor(modelo), dispositivo_resolvido


@lru_cache(maxsize=1)
def carregar_recursos() -> RecursosInferencia:
    verificar_modelos()

    modelo_predicao = carregar_modelo(
        pasta_modelos() / "tomato_mobilenetv2_v5.keras"
    )

    classes = carregar_classes(pasta_modelos() / "classes.txt")

    preditor_sam, dispositivo = carregar_preditor_sam("auto")

    return RecursosInferencia(
        preditor_sam=preditor_sam,
        modelo_predicao=modelo_predicao,
        classes=classes,
        dispositivo=dispositivo,
    )


def nova_pasta_execucao(raiz: Path) -> tuple[str, Path]:
    id_execucao = f"{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:8]}"

    pasta = raiz / id_execucao

    pasta.mkdir(parents=True, exist_ok=False)

    return id_execucao, pasta


def analisar(
    imagem: str | Path,
    *,
    raiz_resultados: str | Path | None = None,
    diagnosticos: bool = False,
) -> ResultadoAnalise:
    origem = Path(imagem)

    if origem.suffix.lower() not in {".jpg", ".jpeg"}:
        raise ValueError("Formato não suportado. Use JPEG ou JPG.")

    recursos = carregar_recursos()

    raiz = Path(raiz_resultados or settings.RESULTS_ROOT)

    id_execucao, pasta = nova_pasta_execucao(raiz)

    pasta_preprocessamento = pasta / "preprocessamento"

    try:
        inicio_mobilesam = time.perf_counter()

        with torch.inference_mode():
            resultado_preprocessamento = processar_imagem(
                recursos.preditor_sam,
                origem,
                pasta_preprocessamento,
                diagnosticos=diagnosticos,
                dispositivo=recursos.dispositivo,
            )

        tempo_mobilesam_ms = (time.perf_counter() - inicio_mobilesam) * 1000

        resultado_classificacao = classificar(
            recursos.modelo_predicao,
            recursos.classes,
            resultado_preprocessamento.arquivo_saida,
        )

        salvar_classificacao(resultado_classificacao, pasta / "predicao.json")

        resultado = ResultadoAnalise(
            id_execucao=id_execucao,
            pasta_execucao=str(pasta.resolve()),
            arquivo_original=str(origem.resolve()),
            arquivo_analisado=resultado_preprocessamento.arquivo_saida,
            preprocessamento=resultado_preprocessamento,
            classificacao=resultado_classificacao,
            aviso_fallback=resultado_preprocessamento.status == "fallback_roi",
            tempo_mobilesam_ms=round(tempo_mobilesam_ms, 3),
        )

        (pasta / "resultado_completo.json").write_text(
            json.dumps(asdict(resultado), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return resultado
    except Exception as erro:
        (pasta / "erro.json").write_text(
            json.dumps(
                {"tipo": type(erro).__name__, "mensagem": str(erro)},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        raise
