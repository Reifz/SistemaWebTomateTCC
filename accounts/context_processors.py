from alerts.models import Alert
from captures.models import Capture
from predictions.models import Prediction
from sensors.models import EnvironmentalReading


def resumo_dados_administrativos(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return {}
    modelo_usuario = request.user._meta.model
    return {
        "resumo_dados_administrativos": {
            "usuarios_ativos": modelo_usuario.objects.filter(is_active=True).count(),
            "capturas": Capture.objects.count(),
            "leituras": EnvironmentalReading.objects.count(),
            "previsoes": Prediction.objects.count(),
            "alertas": Alert.objects.count(),
        }
    }
