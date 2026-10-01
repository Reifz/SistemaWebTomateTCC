from alerts.models import Alerta
from captures.models import Captura
from predictions.models import Predicao
from sensors.models import LeituraAmbiental


def resumo_dados_administrativos(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return {}

    modelo_usuario = request.user._meta.model

    return {
        "resumo_dados_administrativos": {
            "usuarios_ativos": modelo_usuario.objects.filter(is_active=True).count(),
            "capturas": Captura.objects.count(),
            "leituras": LeituraAmbiental.objects.count(),
            "previsoes": Predicao.objects.count(),
            "alertas": Alerta.objects.count(),
        }
    }
