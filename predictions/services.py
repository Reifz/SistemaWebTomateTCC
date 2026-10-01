import logging
import random
import threading
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.db import transaction
from PIL import Image, UnidentifiedImageError

from alerts.services import criar_alertas_da_predicao
from captures.models import Captura
from predictions.models import Predicao
from sensors.models import LeituraAmbiental

registrador = logging.getLogger(__name__)

BLOQUEIO_INFERENCIA = threading.Lock()

NOME_MODELO = "MobileNetV2_Tomato_Modelo_B_v5"


class ErroProcessamento(RuntimeError):
    """Erro conhecido durante o processamento de uma captura."""


class ImagemInvalida(ErroProcessamento):
    """A captura não possui uma imagem JPEG íntegra."""


class LeituraInvalida(ErroProcessamento):
    """A leitura ambiental está fora das faixas definidas no TCC."""


class ProcessamentoEmAndamento(ErroProcessamento):
    """A captura já está sendo analisada por outra requisição."""


class ModeloIndisponivel(ErroProcessamento):
    """Os pesos necessários não estão disponíveis ou íntegros."""


def executar_analise_real(caminho_imagem):
    try:
        from predictions.inferencia import ErroArtefatoModelo, analisar

        return analisar(caminho_imagem)
    except ErroArtefatoModelo as erro:
        raise ModeloIndisponivel(str(erro)) from erro


def nivel_confianca(confianca):
    valor = Decimal(str(confianca))

    if valor < 60:
        return Predicao.NivelConfianca.BAIXA

    if valor < 80:
        return Predicao.NivelConfianca.MEDIA

    return Predicao.NivelConfianca.ALTA


def gerar_leitura_ambiental(captura, temperatura=None, umidade=None, gerador=None):
    """Registra a leitura informada ou gera valores somente para dados demonstrativos."""

    gerador = gerador or random.SystemRandom()

    temperatura = temperatura if temperatura is not None else round(gerador.uniform(18, 35), 2)

    umidade = umidade if umidade is not None else round(gerador.uniform(50, 95), 2)

    return LeituraAmbiental.objects.create(
        captura=captura,
        temperatura=temperatura,
        umidade=umidade,
    )


def _validar_captura(captura):
    if not captura.imagem:
        raise ImagemInvalida("A captura não possui imagem para análise.")

    caminho = Path(captura.imagem.path)

    if caminho.suffix.lower() not in {".jpg", ".jpeg"}:
        raise ImagemInvalida("A imagem deve estar no formato JPEG ou JPG.")

    try:
        with Image.open(caminho) as imagem:
            imagem.verify()
    except (OSError, UnidentifiedImageError) as erro:
        raise ImagemInvalida("A imagem está inválida ou corrompida.") from erro

    leitura = getattr(captura, "leitura_ambiental", None)

    if leitura is None:
        return

    if not Decimal("0") <= leitura.temperatura <= Decimal("60"):
        raise LeituraInvalida("A temperatura deve estar entre 0 °C e 60 °C.")

    if not Decimal("0") <= leitura.umidade <= Decimal("100"):
        raise LeituraInvalida("A umidade deve estar entre 0% e 100%.")


def _caminho_relativo_resultado(caminho):
    return Path(caminho).resolve().relative_to(Path(settings.RESULTS_ROOT).resolve()).as_posix()


def _marcar_erro(id_captura):
    Captura.objects.filter(pk=id_captura).exclude(
        status=Captura.Status.PROCESSADA
    ).update(status=Captura.Status.ERRO)


def processar_captura(captura, executor_analise=None):
    """Executa MobileSAM e MobileNetV2, persistindo um único resultado por captura."""

    executor = executor_analise or executar_analise_real

    try:
        with transaction.atomic():
            captura_bloqueada = Captura.objects.select_for_update().select_related(
                "leitura_ambiental"
            ).get(pk=captura.pk)

            predicao_existente = Predicao.objects.filter(
                captura=captura_bloqueada
            ).first()

            if predicao_existente:
                return predicao_existente, False

            if captura_bloqueada.status == Captura.Status.PROCESSANDO:
                raise ProcessamentoEmAndamento("A captura já está sendo processada.")

            _validar_captura(captura_bloqueada)

            captura_bloqueada.status = Captura.Status.PROCESSANDO

            captura_bloqueada.save(update_fields=["status"])
    except ProcessamentoEmAndamento:
        raise
    except (ImagemInvalida, LeituraInvalida):
        _marcar_erro(captura.pk)

        raise

    registrador.info("Iniciando inferência real da captura %s.", captura.pk)

    try:
        with BLOQUEIO_INFERENCIA:
            resultado = executor(captura_bloqueada.imagem.path)
    except Exception:
        _marcar_erro(captura.pk)

        registrador.exception("Falha na inferência real da captura %s.", captura.pk)

        raise

    classificacao = resultado.classificacao

    tres_principais = [
        {"class": item["classe"], "confidence": item["percentual"]}
        for item in classificacao.principais_predicoes[:3]
    ]

    with transaction.atomic():
        captura_bloqueada = Captura.objects.select_for_update().get(pk=captura.pk)

        predicao_existente = Predicao.objects.filter(
            captura=captura_bloqueada
        ).first()

        if predicao_existente:
            return predicao_existente, False

        predicao = Predicao.objects.create(
            captura=captura_bloqueada,
            classe_prevista=classificacao.classe_prevista,
            confianca=Decimal(str(classificacao.confianca_percentual)).quantize(Decimal("0.01")),
            tres_principais=tres_principais,
            nivel_confianca=nivel_confianca(classificacao.confianca_percentual),
            modelo_utilizado=NOME_MODELO,
            id_execucao=resultado.id_execucao,
            status_preprocessamento=resultado.preprocessamento.status,
            caminho_imagem_processada=_caminho_relativo_resultado(resultado.preprocessamento.arquivo_saida),
            caminho_imagem_guia=_caminho_relativo_resultado(resultado.preprocessamento.arquivo_guia),
            tempo_inferencia_ms=classificacao.tempo_inferencia_ms,
            tempo_mobilesam_ms=Decimal(str(resultado.tempo_mobilesam_ms)),
            dispositivo_processamento=resultado.preprocessamento.dispositivo,
            motivos_fallback=resultado.preprocessamento.motivos,
        )

        criar_alertas_da_predicao(predicao)

        captura_bloqueada.status = Captura.Status.PROCESSADA

        captura_bloqueada.save(update_fields=["status"])

    registrador.info(
        "Inferência concluída para a captura %s em %s ms; MobileSAM em %s ms.",
        captura.pk,
        predicao.tempo_inferencia_ms,
        predicao.tempo_mobilesam_ms,
    )

    if predicao.status_preprocessamento == Predicao.StatusPreprocessamento.FALLBACK_ROI:
        registrador.warning(
            "Captura %s processada com fallback_roi: %s.",
            captura.pk,
            ", ".join(predicao.motivos_fallback),
        )

    return predicao, True
