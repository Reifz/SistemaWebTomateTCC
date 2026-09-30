from decimal import Decimal
from .models import Alert


def criar_alertas_da_predicao(predicao):
    """
    Avalia os resultados de uma predição e as condições ambientais da captura
    para gerar e salvar automaticamente os alertas correspondentes.
    
    Regras de geração de alertas:
    1. Confiança < 60%: Alerta de Baixa Confiança (Severidade Média)
    2. Doença com Confiança >= 80%: Alerta Fitossanitário (Severidade Alta)
    3. Doença com Confiança >= 80% + Umidade >= 85%: Alerta Crítico (Severidade Crítica)
    4. Umidade >= 85%: Alerta Ambiental (Severidade Média)
    """
    captura = predicao.capture
    confianca = Decimal(predicao.confidence)
    
    # Obtém a umidade da leitura ambiental se houver registro vinculado à captura
    umidade = None
    if hasattr(captura, "environmental_reading"):
        umidade = Decimal(captura.environmental_reading.humidity)
        
    # Identifica se a classe identificada indica presença de patógeno/doença
    tem_doenca = predicao.predicted_class != "Tomato___healthy"
    alertas = []

    def adicionar(tipo, severidade, mensagem):
        """Função auxiliar interna para instanciar objetos Alert na lista temporária."""
        alertas.append(
            Alert(
                capture=captura, 
                prediction=predicao, 
                type=tipo, 
                severity=severidade, 
                message=mensagem
            )
        )

    # 1. Alerta de baixa confiança na inferência (solicita nova captura)
    if confianca < 60:
        adicionar(
            Alert.Type.LOW_CONFIDENCE, 
            Alert.Severity.MEDIUM, 
            "Baixa confiança na análise. Recomenda-se realizar uma nova captura."
        )
        
    # 2. Alerta fitossanitário para detecção de doença com alta confiabilidade
    if tem_doenca and confianca >= 80:
        adicionar(
            Alert.Type.PHYTOSANITARY, 
            Alert.Severity.HIGH, 
            f"Possível doença detectada: {predicao.predicted_class}."
        )
        
    # 3. Alerta crítico quando a presença de doença com alta confiança coincide com clima propício (umidade alta)
    if tem_doenca and confianca >= 80 and umidade is not None and umidade >= 85:
        adicionar(
            Alert.Type.CRITICAL, 
            Alert.Severity.CRITICAL, 
            "Doença com alta confiança associada a umidade elevada. Recomenda-se inspeção imediata."
        )
        
    # 4. Alerta ambiental preventivo focado na condição de umidade excessiva na lavoura
    if umidade is not None and umidade >= 85:
        adicionar(
            Alert.Type.ENVIRONMENTAL, 
            Alert.Severity.MEDIUM, 
            "Umidade elevada detectada; monitore condições favoráveis a doenças."
        )
        
    # Otimização de banco de dados: insere todos os alertas gerados em uma única query SQL
    return Alert.objects.bulk_create(alertas)