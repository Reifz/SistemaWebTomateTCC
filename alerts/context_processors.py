from .models import Alerta


def quantidade_alertas_nao_lidos(request):
    if not request.user.is_authenticated:
        return {"quantidade_alertas_nao_lidos": 0}

    alertas = Alerta.objects.all() if request.user.is_staff else Alerta.objects.filter(captura__usuario=request.user)

    return {"quantidade_alertas_nao_lidos": alertas.filter(visualizado=False).count()}
