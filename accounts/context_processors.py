from alerts.models import Alerta
from captures.models import Captura
from predictions.models import Predicao
from sensors.models import LeituraAmbiental


def resumo_dados_administrativos(request):
    """
    Context Processor do Django que disponibiliza dados estatísticos gerais do sistema
    para os templates.
    
    Apenas usuários autenticados e membros da equipe/staff (`is_staff=True`) recebem
    o dicionário com o resumo dos dados operacionais.
    """
    # Controle de acesso: se o usuário não estiver autenticado ou não for staff, retorna um dicionário vazio
    if not request.user.is_authenticated or not request.user.is_staff:
        return {}

    # Obtém dinamicamente o model de usuário configurado na aplicação a partir da instância da requisição
    modelo_usuario = request.user._meta.model

    # Retorna as métricas que ficarão disponíveis no contexto global de renderização dos templates
    return {
        "resumo_dados_administrativos": {
            "usuarios_ativos": modelo_usuario.objects.filter(is_active=True).count(),
            "capturas": Captura.objects.count(),
            "leituras": LeituraAmbiental.objects.count(),
            "previsoes": Predicao.objects.count(),
            "alertas": Alerta.objects.count(),
        }
    }