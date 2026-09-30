from alerts.models import Alert
from captures.models import Capture
from predictions.models import Prediction
from sensors.models import EnvironmentalReading


def resumo_dados_administrativos(request):
    """
    Context Processor do Django responsável por disponibilizar métricas e estatísticas
    globais do sistema para os templates.
    
    Apenas usuários autenticados com status de equipe/staff (`is_staff=True`) possuem
    acesso aos dados resumidos.
    """
    # Validações de segurança: retorna dicionário vazio se o usuário não for autenticado ou não for staff
    if not request.user.is_authenticated or not request.user.is_staff:
        return {}
        
    # Obtém a classe do Model de usuário configurado na aplicação dinamicamente a partir da instância da requisição
    modelo_usuario = request.user._meta.model
    
    # Retorna o dicionário de contexto que estará disponível globalmente nos templates
    return {
        "resumo_dados_administrativos": {
            "usuarios_ativos": modelo_usuario.objects.filter(is_active=True).count(),
            "capturas": Capture.objects.count(),
            "leituras": EnvironmentalReading.objects.count(),
            "previsoes": Prediction.objects.count(),
            "alertas": Alert.objects.count(),
        }
    }