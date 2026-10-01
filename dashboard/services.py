import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.db.models import Avg, Count
from django.urls import reverse
from django.utils import timezone
from alerts.models import Alerta
from captures.models import Captura
from predictions.models import Predicao
from sensors.models import LeituraAmbiental

CLASSE_SAUDAVEL = "Tomato___healthy"

QUANTIDADE_DIAS_ALERTAS = 30


def resumo_painel(usuario, usuario_selecionado=None):
    capturas = _capturas_visiveis(usuario, usuario_selecionado)

    predicoes = Predicao.objects.filter(captura__in=capturas)

    alertas = Alerta.objects.filter(captura__in=capturas)

    leituras_ambientais = LeituraAmbiental.objects.filter(captura__in=capturas)

    distribuicao = list(
        predicoes.values("classe_prevista")
        .annotate(total=Count("id"))
        .order_by("classe_prevista")
    )

    leituras_recentes = list(
        leituras_ambientais.order_by("-medida_em").values(
            "medida_em",
            "temperatura",
            "umidade",
        )[:10]
    )

    leituras_recentes.reverse()

    estatisticas_classes = _estatisticas_por_classe(predicoes)

    alertas_temporais = _alertas_por_dia(alertas)

    return {
        "total_capturas": capturas.count(),
        "capturas_processadas": capturas.filter(status=Captura.Status.PROCESSADA).count(),
        "alertas_ativos": alertas.filter(visualizado=False).count(),
        "ultima_temperatura": _valor_ultima_leitura(leituras_ambientais, "temperatura"),
        "ultima_umidade": _valor_ultima_leitura(leituras_ambientais, "umidade"),
        "ultima_predicao": predicoes.first(),
        "doencas_detectadas": predicoes.exclude(classe_prevista=CLASSE_SAUDAVEL).count(),
        "baixa_confianca": predicoes.filter(confianca__lt=60).count(),
        "distribuicao": distribuicao,
        "leituras": leituras_recentes,
        "estatisticas_classes": estatisticas_classes,
        "principais_classes": _cinco_classes_mais_detectadas(estatisticas_classes),
        "linha_tempo_alertas": alertas_temporais,
        "linha_tempo_alertas_possui_dados": _alertas_temporais_possuem_dados(alertas_temporais),
    }


def _capturas_visiveis(usuario, usuario_selecionado=None):
    if usuario.is_staff:
        capturas = Captura.objects.all()

        if usuario_selecionado:
            capturas = capturas.filter(usuario=usuario_selecionado)

        return capturas

    return Captura.objects.filter(usuario=usuario)


def _valor_ultima_leitura(leituras, campo):
    ultima_leitura = leituras.first()

    return getattr(ultima_leitura, campo) if ultima_leitura else None


def _estatisticas_por_classe(predicoes):
    estatisticas = list(
        predicoes.values("classe_prevista")
        .annotate(total=Count("id"), confianca_media=Avg("confianca"))
        .order_by("-confianca_media", "classe_prevista")
    )

    for item in estatisticas:
        item["confianca_media"] = round(float(item["confianca_media"]), 2)

    return estatisticas


def _cinco_classes_mais_detectadas(estatisticas):
    return sorted(
        estatisticas,
        key=lambda item: (-item["total"], item["classe_prevista"]),
    )[:5]


def _alertas_temporais_possuem_dados(alertas_temporais):
    severidades = (
        Alerta.Severidade.BAIXA,
        Alerta.Severidade.MEDIA,
        Alerta.Severidade.ALTA,
        Alerta.Severidade.CRITICA,
    )

    return any(
        item[severidade]
        for item in alertas_temporais
        for severidade in severidades
    )


def _alertas_por_dia(alertas):
    hoje = timezone.localdate()

    inicio = hoje - timedelta(days=QUANTIDADE_DIAS_ALERTAS - 1)

    inicio_periodo = timezone.make_aware(datetime.combine(inicio, datetime.min.time()))

    fim_periodo = timezone.make_aware(datetime.combine(hoje + timedelta(days=1), datetime.min.time()))

    severidades = [
        Alerta.Severidade.BAIXA,
        Alerta.Severidade.MEDIA,
        Alerta.Severidade.ALTA,
        Alerta.Severidade.CRITICA,
    ]

    contagens = Counter()

    for criado_em, severidade in alertas.filter(
        criado_em__gte=inicio_periodo,
        criado_em__lt=fim_periodo,
    ).values_list("criado_em", "severidade"):
        dia = timezone.localtime(criado_em).date()

        if dia <= hoje:
            contagens[(dia, severidade)] += 1

    return [
        {
            "data": (inicio + timedelta(days=indice)).isoformat(),
            **{
                severidade: contagens[(inicio + timedelta(days=indice), severidade)]
                for severidade in severidades
            },
        }
        for indice in range(QUANTIDADE_DIAS_ALERTAS)
    ]


def resultados_manuais():
    """Lê resultados do disco sem alterar o banco de dados."""

    raiz = Path(settings.RESULTS_ROOT)

    if not raiz.is_dir():
        return []

    resultados = []

    for pasta_execucao in sorted((item for item in raiz.iterdir() if item.is_dir()), reverse=True):
        arquivo_predicao = pasta_execucao / "predicao.json"

        if not arquivo_predicao.is_file():
            continue

        try:
            predicao = json.loads(arquivo_predicao.read_text(encoding="utf-8"))

            data_captura = timezone.make_aware(datetime.strptime(pasta_execucao.name[:15], "%Y%m%d_%H%M%S"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue

        principais_predicoes = predicao.get("principais_predicoes", [])[:3]

        resultados.append({
            "id": pasta_execucao.name,
            "capturada_em": data_captura,
            "classe_prevista": predicao.get("classe_prevista", "Resultado indisponível").replace("Tomato___", "").replace("_", " "),
            "confianca": predicao.get("confianca_percentual", 0),
            "nivel_confianca": predicao.get("nivel_confianca", "não informado"),
            "tempo_inferencia_ms": predicao.get("tempo_inferencia_ms"),
            "principais_predicoes": [
                {
                    "classe": item.get("classe", "").replace("Tomato___", "").replace("_", " "),
                    "percentual": item.get("percentual", 0),
                }
                for item in principais_predicoes
            ],
            "url_original": reverse("imagem_resultado_manual", args=(pasta_execucao.name, "original")),
            "url_processada": reverse("imagem_resultado_manual", args=(pasta_execucao.name, "processed")),
            "url_guia": reverse("imagem_resultado_manual", args=(pasta_execucao.name, "guide")),
        })

    return resultados
