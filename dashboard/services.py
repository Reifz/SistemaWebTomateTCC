import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.db.models import Avg, Count
from django.urls import reverse
from django.utils import timezone
from alerts.models import Alert
from captures.models import Capture
from predictions.models import Prediction
from sensors.models import EnvironmentalReading

# Constantes globais
CLASSE_SAUDAVEL = "Tomato___healthy"
QUANTIDADE_DIAS_ALERTAS = 30


def resumo_dashboard(usuario, usuario_selecionado=None):
    """
    Função principal que consolida todas as métricas, dados estatísticos,
    leituras de sensores e séries temporais para o painel do usuário.
    """
    # Define o escopo das capturas com base nas permissões e seleções de usuário
    capturas = _capturas_visiveis(usuario, usuario_selecionado)
    
    # Consulta os relacionamentos com base nas capturas filtradas
    predicoes = Prediction.objects.filter(capture__in=capturas)
    alertas = Alert.objects.filter(capture__in=capturas)
    leituras_ambientais = EnvironmentalReading.objects.filter(capture__in=capturas)

    # Agrupa e conta a distribuição por classe prevista
    distribuicao = list(
        predicoes.values("predicted_class")
        .annotate(total=Count("id"))
        .order_by("predicted_class")
    )
    
    # Obtém as 10 leituras de sensores mais recentes e inverte a ordem para exibição cronológica
    leituras_recentes = list(
        leituras_ambientais.order_by("-measured_at").values(
            "measured_at",
            "temperature",
            "humidity",
        )[:10]
    )
    leituras_recentes.reverse()

    # Processa estatísticas detalhadas de classes e histórico de alertas
    estatisticas_classes = _estatisticas_por_classe(predicoes)
    alertas_temporais = _alertas_por_dia(alertas)
    
    # Monta o dicionário de resposta com todas as métricas consolidadas
    return {
        "total_captures": capturas.count(),
        "processed_captures": capturas.filter(status=Capture.Status.PROCESSED).count(),
        "active_alerts": alertas.filter(viewed=False).count(),
        "latest_temperature": _valor_ultima_leitura(leituras_ambientais, "temperature"),
        "latest_humidity": _valor_ultima_leitura(leituras_ambientais, "humidity"),
        "latest_prediction": predicoes.first(),
        "diseases_detected": predicoes.exclude(predicted_class=CLASSE_SAUDAVEL).count(),
        "low_confidence": predicoes.filter(confidence__lt=60).count(),
        "distribution": distribuicao,
        "readings": leituras_recentes,
        "class_statistics": estatisticas_classes,
        "top_classes": _cinco_classes_mais_detectadas(estatisticas_classes),
        "alerts_timeline": alertas_temporais,
        "alerts_timeline_has_data": _alertas_temporais_possuem_dados(alertas_temporais),
    }


def _capturas_visiveis(usuario, usuario_selecionado=None):
    """
    Retorna o QuerySet de capturas acessíveis:
    - Para equipe/staff: todas as capturas ou filtradas por um usuário específico.
    - Para usuários comuns: apenas as próprias capturas.
    """
    if usuario.is_staff:
        capturas = Capture.objects.all()
        if usuario_selecionado:
            capturas = capturas.filter(user=usuario_selecionado)
        return capturas
    return Capture.objects.filter(user=usuario)


def _valor_ultima_leitura(leituras, campo):
    """Retorna o valor de um campo específico da leitura ambiental mais recente."""
    ultima_leitura = leituras.first()
    return getattr(ultima_leitura, campo) if ultima_leitura else None


def _estatisticas_por_classe(predicoes):
    """
    Calcula o total de ocorrências e a confiança média agrupados por classe prevista,
    ordenando da maior para a menor confiança.
    """
    estatisticas = list(
        predicoes.values("predicted_class")
        .annotate(total=Count("id"), confianca_media=Avg("confidence"))
        .order_by("-confianca_media", "predicted_class")
    )
    # Arredonda a média de confiança para duas casas decimais
    for item in estatisticas:
        item["confianca_media"] = round(float(item["confianca_media"]), 2)
    return estatisticas


def _cinco_classes_mais_detectadas(estatisticas):
    """Retorna as 5 classes com maior quantidade total de detecções."""
    return sorted(
        estatisticas,
        key=lambda item: (-item["total"], item["predicted_class"]),
    )[:5]


def _alertas_temporais_possuem_dados(alertas_temporais):
    """Verifica se há pelo menos um alerta registrado no período analisado."""
    severidades = (
        Alert.Severity.LOW,
        Alert.Severity.MEDIUM,
        Alert.Severity.HIGH,
        Alert.Severity.CRITICAL,
    )
    return any(
        item[severidade]
        for item in alertas_temporais
        for severidade in severidades
    )


def _alertas_por_dia(alertas):
    """Retorna uma série contínua de 30 dias, inclusive nos dias sem alertas."""
    hoje = timezone.localdate()
    inicio = hoje - timedelta(days=QUANTIDADE_DIAS_ALERTAS - 1)
    inicio_periodo = timezone.make_aware(datetime.combine(inicio, datetime.min.time()))
    fim_periodo = timezone.make_aware(datetime.combine(hoje + timedelta(days=1), datetime.min.time()))
    
    severidades = [
        Alert.Severity.LOW,
        Alert.Severity.MEDIUM,
        Alert.Severity.HIGH,
        Alert.Severity.CRITICAL,
    ]
    
    # Contabiliza a ocorrência de alertas agrupados por dia e grau de severidade
    contagens = Counter()
    for criado_em, severidade in alertas.filter(
        created_at__gte=inicio_periodo,
        created_at__lt=fim_periodo,
    ).values_list("created_at", "severity"):
        dia = timezone.localtime(criado_em).date()
        if dia <= hoje:
            contagens[(dia, severidade)] += 1
            
    # Constrói a lista estruturada garantindo entradas contínuas para os 30 dias
    return [
        {
            "date": (inicio + timedelta(days=indice)).isoformat(),
            **{
                severidade: contagens[(inicio + timedelta(days=indice), severidade)]
                for severidade in severidades
            },
        }
        for indice in range(QUANTIDADE_DIAS_ALERTAS)
    ]


def resultados_manuais():
    """Lê resultados do disco sem importá-los para o banco de dados."""
    raiz = Path(settings.RESULTS_ROOT)
    if not raiz.is_dir():
        return []

    resultados = []
    # Percorre as pastas de execução em ordem decrescente
    for pasta_execucao in sorted((item for item in raiz.iterdir() if item.is_dir()), reverse=True):
        arquivo_predicao = pasta_execucao / "predicao.json"
        if not arquivo_predicao.is_file():
            continue
            
        # Tenta carregar o JSON e extrair a data pelo nome da pasta
        try:
            predicao = json.loads(arquivo_predicao.read_text(encoding="utf-8"))
            data_captura = timezone.make_aware(datetime.strptime(pasta_execucao.name[:15], "%Y%m%d_%H%M%S"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue

        # Formata as principais predições e URLs de imagens associadas
        principais_predicoes = predicao.get("principais_predicoes", [])[:3]
        resultados.append({
            "id": pasta_execucao.name,
            "captured_at": data_captura,
            "predicted_class": predicao.get("classe_prevista", "Resultado indisponível").replace("Tomato___", "").replace("_", " "),
            "confidence": predicao.get("confianca_percentual", 0),
            "confidence_level": predicao.get("nivel_confianca", "não informado"),
            "inference_ms": predicao.get("tempo_inferencia_ms"),
            "top_predictions": [
                {
                    "class": item.get("classe", "").replace("Tomato___", "").replace("_", " "),
                    "percentage": item.get("percentual", 0),
                }
                for item in principais_predicoes
            ],
            "original_url": reverse("manual_result_image", args=(pasta_execucao.name, "original")),
            "processed_url": reverse("manual_result_image", args=(pasta_execucao.name, "processed")),
            "guide_url": reverse("manual_result_image", args=(pasta_execucao.name, "guide")),
        })
    return resultados