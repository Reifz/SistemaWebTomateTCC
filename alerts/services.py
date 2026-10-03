from decimal import Decimal

from .models import Alerta


def criar_alertas_da_predicao(predicao):
    """
    Avalia a predição de IA e as leituras ambientais associadas a uma captura
    para gerar no máximo um alerta no banco de dados.
    
    A lógica segue a ordem estrita de prioridade de regras de negócio (RN09–RN12):
    1. Crítico (Doença + Confiança >= 80% + Umidade >= 85%)
    2. Fitossanitário (Doença + Confiança >= 80%)
    3. Baixa Confiança (Confiança < 60%)
    4. Ambiental (Umidade >= 85%)
    
    Retorna uma lista contendo o alerta criado ou uma lista vazia caso nenhuma regra seja atendida.
    """
    # Obtém a captura de imagem vinculada a esta predição
    captura = predicao.captura

    # Converte o valor de confiança para Decimal para garantir precisão nas comparações numéricas
    confianca = Decimal(predicao.confianca)

    # Tenta obter a leitura ambiental (sensores) associada à captura, se existir
    leitura = getattr(captura, "leitura_ambiental", None)

    # Converte a umidade para Decimal caso a leitura ambiental esteja disponível
    umidade = Decimal(leitura.umidade) if leitura is not None else None

    # Identifica se a IA detectou alguma doença (qualquer classe diferente de tomate saudável)
    tem_doenca = predicao.classe_prevista != "Tomato___healthy"

    # Tupla que armazenará (Tipo, Severidade, Mensagem) se alguma condição for satisfeita
    dados_alerta = None

    # Prioridade 1 (RN09): Doença detectada com alta confiança E alta umidade (condição crítica de risco)
    if tem_doenca and confianca >= 80 and umidade is not None and umidade >= 85:
        dados_alerta = (
            Alerta.Tipo.CRITICO,
            Alerta.Severidade.CRITICA,
            "Doença com alta confiança associada a umidade elevada. Recomenda-se inspeção imediata.",
        )

    # Prioridade 2 (RN10): Doença detectada com alta confiança, sem umidade crítica necessária
    elif tem_doenca and confianca >= 80:
        dados_alerta = (
            Alerta.Tipo.FITOSSANITARIO,
            Alerta.Severidade.ALTA,
            f"Possível doença detectada: {predicao.classe_prevista}.",
        )

    # Prioridade 3 (RN11): Confiança da IA muito baixa, sugerindo refazer a imagem
    elif confianca < 60:
        dados_alerta = (
            Alerta.Tipo.BAIXA_CONFIANCA,
            Alerta.Severidade.MEDIA,
            "Baixa confiança na análise. Recomenda-se realizar uma nova captura.",
        )

    # Prioridade 4 (RN12): Sem alerta de doença/baixa confiança, mas com umidade alta
    elif umidade is not None and umidade >= 85:
        dados_alerta = (
            Alerta.Tipo.AMBIENTAL,
            Alerta.Severidade.MEDIA,
            "Umidade elevada detectada; monitore condições favoráveis a doenças.",
        )

    # Se nenhuma das regras de negócio foi atendida, não gera nenhum alerta
    if dados_alerta is None:
        return []

    # Persiste o novo registro de alerta no banco de dados
    alerta = Alerta.objects.create(
        captura=captura,
        predicao=predicao,
        tipo=dados_alerta[0],
        severidade=dados_alerta[1],
        mensagem=dados_alerta[2],
    )

    # Retorna o alerta gerado dentro de uma lista
    return [alerta]