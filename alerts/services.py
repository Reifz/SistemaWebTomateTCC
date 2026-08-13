from decimal import Decimal
from .models import Alert


def criar_alertas_da_predicao(predicao):
    captura = predicao.capture
    confianca = Decimal(predicao.confidence)
    umidade = None
    if hasattr(captura, "environmental_reading"):
        umidade = Decimal(captura.environmental_reading.humidity)
    tem_doenca = predicao.predicted_class != "Tomato___healthy"
    alertas = []

    def adicionar(tipo, severidade, mensagem):
        alertas.append(Alert(capture=captura, prediction=predicao, type=tipo, severity=severidade, message=mensagem))

    if confianca < 60:
        adicionar(Alert.Type.LOW_CONFIDENCE, Alert.Severity.MEDIUM, "Baixa confiança na análise. Recomenda-se realizar uma nova captura.")
    if tem_doenca and confianca >= 80:
        adicionar(Alert.Type.PHYTOSANITARY, Alert.Severity.HIGH, f"Possível doença detectada: {predicao.predicted_class}.")
    if tem_doenca and confianca >= 80 and umidade is not None and umidade >= 85:
        adicionar(Alert.Type.CRITICAL, Alert.Severity.CRITICAL, "Doença com alta confiança associada a umidade elevada. Recomenda-se inspeção imediata.")
    if umidade is not None and umidade >= 85:
        adicionar(Alert.Type.ENVIRONMENTAL, Alert.Severity.MEDIUM, "Umidade elevada detectada; monitore condições favoráveis a doenças.")
    return Alert.objects.bulk_create(alertas)
