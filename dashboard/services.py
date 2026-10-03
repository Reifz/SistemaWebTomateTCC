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

# Constantes globais do serviço de métricas do painel
CLASSE_SAUDAVEL = "Tomato___healthy"
QUANTIDADE_DIAS_ALERTAS = 30


def resumo_painel(usuario, usuario_selecionado=None):
    """
    Consolida e retorna todas as métricas e estatísticas agregadas para exibição no dashboard.
    
    Aplica controle de visibilidade multitenant/staff e agrupa informações de capturas,
    predições da IA, leituras de sensores ambientais e histórico temporal de alertas.
    """
    capturas = _capturas_visiveis(usuario, usuario_selecionado)

    # Filtra os relacionamentos associados apenas às capturas visíveis ao usuário
    predicoes = Predicao.objects.filter(captura__in=capturas)
    alertas = Alerta.objects.filter(captura__in=capturas)
    leituras_ambientais = LeituraAmbiental.objects.filter(captura__in=capturas)

    # Distribuição do total de diagnósticos/predições agrupados por classe
    distribuicao = list(
        predicoes.values("classe_prevista")
        .annotate(total=Count("id"))
        .order_by("classe_prevista")
    )

    # Recupera as 10 leituras mais recentes dos sensores ambientais e reverte a ordem para cronológica
    leituras_recentes = list(
        leituras_ambientais.order_by("-medida_em").values(
            "medida_em",
            "temperatura",
            "umidade",
        )[:10]
    )
    leituras_recentes.reverse()

    # Cálculo de métricas secundárias e agregados estatísticos
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
    """
    Função utilitária interna para filtrar o QuerySet base de capturas.
    Se o usuário for da equipe de suporte (staff), permite visualizar todas as capturas
    ou filtrar por um usuário específico. Caso contrário, restringe estritamente ao próprio usuário.
    """
    if usuario.is_staff:
        capturas = Captura.objects.all()

        if usuario_selecionado:
            capturas = capturas.filter(usuario=usuario_selecionado)

        return capturas

    return Captura.objects.filter(usuario=usuario)


def _valor_ultima_leitura(leituras, campo):
    """
    Retorna o valor de um campo específico da última leitura ambiental registrada,
    ou None caso não haja medições cadastradas.
    """
    ultima_leitura = leituras.first()

    return getattr(ultima_leitura, campo) if ultima_leitura else None


def _estatisticas_por_classe(predicoes):
    """
    Calcula o total de ocorrências e a média percentual de confiança para cada
    classe de doença/diagnóstico prevista pelo modelo.
    """
    estatisticas = list(
        predicoes.values("classe_prevista")
        .annotate(total=Count("id"), confianca_media=Avg("confianca"))
        .order_by("-confianca_media", "classe_prevista")
    )

    # Arredonda o valor decimal da confiança média para 2 casas decimais
    for item in estatisticas:
        item["confianca_media"] = round(float(item["confianca_media"]), 2)

    return estatisticas


def _cinco_classes_mais_detectadas(estatisticas):
    """
    Retorna as 5 classes com maior número absoluto de ocorrências detectadas.
    """
    return sorted(
        estatisticas,
        key=lambda item: (-item["total"], item["classe_prevista"]),
    )[:5]


def _alertas_temporais_possuem_dados(alertas_temporais):
    """
    Verifica se a série temporal dos últimos dias possui pelo menos um alerta
    registrado em qualquer nível de severidade.
    """
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
    """
    Agrupa os alertas gerados nos últimos 30 dias (definido por QUANTIDADE_DIAS_ALERTAS),
    contabilizando a frequência por data e por nível de severidade.
    """
    hoje = timezone.localdate()
    inicio = hoje - timedelta(days=QUANTIDADE_DIAS_ALERTAS - 1)

    # Delimita os intervalos com timezone para consulta precisa no banco
    inicio_periodo = timezone.make_aware(datetime.combine(inicio, datetime.min.time()))
    fim_periodo = timezone.make_aware(datetime.combine(hoje + timedelta(days=1), datetime.min.time()))

    severidades = [
        Alerta.Severidade.BAIXA,
        Alerta.Severidade.MEDIA,
        Alerta.Severidade.ALTA,
        Alerta.Severidade.CRITICA,
    ]

    contagens = Counter()

    # Filtra e contabiliza as ocorrências por data local e nível de severidade
    for criado_em, severidade in alertas.filter(
        criado_em__gte=inicio_periodo,
        criado_em__lt=fim_periodo,
    ).values_list("criado_em", "severidade"):
        dia = timezone.localtime(criado_em).date()

        if dia <= hoje:
            contagens[(dia, severidade)] += 1

    # Estrutura e formata o resultado em uma lista ordenada dia a dia em ISO format
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
    """
    Lê diretamente os arquivos de predições manuais gravados no sistema de arquivos
    (diretório RESULTS_ROOT), extraindo metadados e rotas para visualização sem alterar
    o banco de dados.
    """
    raiz = Path(settings.RESULTS_ROOT)

    if not raiz.is_dir():
        return []

    resultados = []

    # Varre as pastas de execução ordenando pelas mais recentes (formato do diretório: YYYYMMDD_HHMMSS)
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

        # Monta a estrutura formatada com rótulos limpos e URLs dinâmicas do Django
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