from decimal import Decimal

from .models import Alerta


def criar_alertas_da_predicao(predicao):
    """Cria no máximo um alerta, respeitando a prioridade RN09–RN12 do TCC."""

    captura = predicao.captura

    confianca = Decimal(predicao.confianca)

    leitura = getattr(captura, "leitura_ambiental", None)

    umidade = Decimal(leitura.umidade) if leitura is not None else None

    tem_doenca = predicao.classe_prevista != "Tomato___healthy"

    dados_alerta = None

    if tem_doenca and confianca >= 80 and umidade is not None and umidade >= 85:
        dados_alerta = (
            Alerta.Tipo.CRITICO,
            Alerta.Severidade.CRITICA,
            "Doença com alta confiança associada a umidade elevada. Recomenda-se inspeção imediata.",
        )

    elif tem_doenca and confianca >= 80:
        dados_alerta = (
            Alerta.Tipo.FITOSSANITARIO,
            Alerta.Severidade.ALTA,
            f"Possível doença detectada: {predicao.classe_prevista}.",
        )

    elif confianca < 60:
        dados_alerta = (
            Alerta.Tipo.BAIXA_CONFIANCA,
            Alerta.Severidade.MEDIA,
            "Baixa confiança na análise. Recomenda-se realizar uma nova captura.",
        )

    elif umidade is not None and umidade >= 85:
        dados_alerta = (
            Alerta.Tipo.AMBIENTAL,
            Alerta.Severidade.MEDIA,
            "Umidade elevada detectada; monitore condições favoráveis a doenças.",
        )

    if dados_alerta is None:
        return []

    alerta = Alerta.objects.create(
        captura=captura,
        predicao=predicao,
        tipo=dados_alerta[0],
        severidade=dados_alerta[1],
        mensagem=dados_alerta[2],
    )

    return [alerta]
