from decimal import Decimal, InvalidOperation

from .models import Alerta


CLASSES_DOENCA = frozenset(
    {
        "Tomato___Bacterial_spot",
        "Tomato___Early_blight",
        "Tomato___Late_blight",
        "Tomato___Leaf_Mold",
        "Tomato___Septoria_leaf_spot",
        "Tomato___Spider_mites Two-spotted_spider_mite",
        "Tomato___Target_Spot",
        "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
        "Tomato___Tomato_mosaic_virus",
    }
)


def validar_valor_ambiental(valor, nome, minimo, maximo, unidade):
    if valor is None:
        return None, f"Não foi possível validar a leitura de {nome}: o valor não foi informado."

    if isinstance(valor, bool):
        return None, f"Não foi possível validar a leitura de {nome}: o valor informado não é numérico."

    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        return None, f"Não foi possível validar a leitura de {nome}: o valor informado não é numérico."

    if not numero.is_finite():
        return None, f"Não foi possível validar a leitura de {nome}: o valor informado não é finito."

    if not minimo <= numero <= maximo:
        return (
            None,
            f"Não foi possível validar a leitura de {nome}: o valor informado está fora da faixa "
            f"de {minimo}{unidade} a {maximo}{unidade}.",
        )

    return numero, None


def criar_alertas_da_predicao(predicao):
    """Cria alertas visuais, ambientais e de leitura que podem coexistir.

    Decisão para H5: umidade >= 85% ou temperatura > 40 °C comprovada por
    uma leitura válida contextualiza uma doença relevante como alerta crítico.
    O tratamento de leituras incompletas complementa RN06, RN07, RN11 e RN12.
    """

    captura = predicao.captura

    confianca = Decimal(predicao.confianca)

    leitura = getattr(captura, "leitura_ambiental", None)

    temperatura, erro_temperatura = validar_valor_ambiental(
        leitura.temperatura if leitura is not None else None,
        "temperatura",
        Decimal("0"),
        Decimal("60"),
        " °C",
    )

    umidade, erro_umidade = validar_valor_ambiental(
        leitura.umidade if leitura is not None else None,
        "umidade",
        Decimal("0"),
        Decimal("100"),
        "%",
    )

    erros_leitura = [erro for erro in (erro_temperatura, erro_umidade) if erro is not None]

    tem_doenca = predicao.classe_prevista in CLASSES_DOENCA

    alertas = []

    temperatura_elevada = temperatura is not None and temperatura > 40

    umidade_elevada = umidade is not None and umidade >= 85

    condicao_ambiental_desfavoravel = temperatura_elevada or umidade_elevada

    if tem_doenca and confianca >= 80 and condicao_ambiental_desfavoravel:
        if temperatura_elevada and umidade_elevada:
            mensagem = (
                "Doença detectada com alta confiança, associada a temperatura e umidade elevadas. "
                "Recomenda-se monitoramento fitossanitário e ambiental prioritário."
            )

        elif umidade_elevada:
            mensagem = (
                "Doença detectada com alta confiança e umidade elevada. "
                "Condição ambiental favorável para o desenvolvimento de doenças."
            )

        else:
            mensagem = (
                "Doença detectada com alta confiança e temperatura elevada. "
                "Recomenda-se monitoramento fitossanitário e ambiental prioritário."
            )

        dados_alerta_principal = (
            Alerta.Tipo.CRITICO,
            Alerta.Severidade.CRITICA,
            mensagem,
        )

    elif tem_doenca and confianca >= 80:
        dados_alerta_principal = (
            Alerta.Tipo.FITOSSANITARIO,
            Alerta.Severidade.ALTA,
            "Doença detectada com alta confiança sem problemas ambientais. "
            "Recomenda-se monitoramento fitossanitário.",
        )

    elif condicao_ambiental_desfavoravel:
        if temperatura_elevada and umidade_elevada:
            mensagem = (
                "Temperatura e umidade elevadas detectadas. "
                "Condição ambiental favorável para o desenvolvimento de doenças."
            )

        elif umidade_elevada:
            mensagem = (
                "Umidade elevada detectada. "
                "Condição ambiental favorável para o desenvolvimento de doenças."
            )

        else:
            mensagem = "Temperatura elevada detectada. Recomenda-se monitoramento ambiental."

        dados_alerta_principal = (
            Alerta.Tipo.AMBIENTAL,
            Alerta.Severidade.MEDIA,
            mensagem,
        )

    else:
        dados_alerta_principal = None

    if dados_alerta_principal is not None:
        alertas.append(
            Alerta.objects.create(
                captura=captura,
                predicao=predicao,
                tipo=dados_alerta_principal[0],
                severidade=dados_alerta_principal[1],
                mensagem=dados_alerta_principal[2],
            )
        )

    if confianca < 60:
        alertas.append(
            Alerta.objects.create(
                captura=captura,
                predicao=predicao,
                tipo=Alerta.Tipo.BAIXA_CONFIANCA,
                severidade=Alerta.Severidade.MEDIA,
                mensagem="Resultado com baixa confiança. Recomenda-se nova captura ou avaliação manual.",
            )
        )

    if erros_leitura:
        conclusao = (
            "A avaliação ambiental ficou indisponível."
            if len(erros_leitura) == 2
            else "A avaliação ambiental ficou incompleta."
        )

        for mensagem in erros_leitura:
            alertas.append(
                Alerta.objects.create(
                    captura=captura,
                    predicao=predicao,
                    tipo=Alerta.Tipo.ERRO_LEITURA,
                    severidade=Alerta.Severidade.MEDIA,
                    mensagem=f"{mensagem} {conclusao}",
                )
            )

    return alertas
