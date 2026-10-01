from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.core.paginator import Paginator
from django.shortcuts import render
from .models import Predicao


@login_required
def historico(request):
    predicoes = Predicao.objects.all() if request.user.is_staff else Predicao.objects.filter(captura__usuario=request.user)

    predicoes = predicoes.select_related("captura", "captura__usuario").prefetch_related("alertas")

    if request.GET.get("q"):
        predicoes = predicoes.filter(
            Q(classe_prevista__icontains=request.GET["q"]) |
            Q(captura__observacao__icontains=request.GET["q"])
        )

    if request.user.is_staff and request.GET.get("user"):
        predicoes = predicoes.filter(captura__usuario_id=request.GET["user"])

    if request.GET.get("date_from"):
        predicoes = predicoes.filter(prevista_em__date__gte=request.GET["date_from"])

    if request.GET.get("date_to"):
        predicoes = predicoes.filter(prevista_em__date__lte=request.GET["date_to"])

    if request.GET.get("class"):
        predicoes = predicoes.filter(classe_prevista=request.GET["class"])

    if request.GET.get("severity"):
        predicoes = predicoes.filter(alertas__severidade=request.GET["severity"])

    if request.GET.get("confidence") == "low":
        predicoes = predicoes.filter(confianca__lt=60)
    elif request.GET.get("confidence") == "medium":
        predicoes = predicoes.filter(confianca__gte=60, confianca__lt=80)
    elif request.GET.get("confidence") == "high":
        predicoes = predicoes.filter(confianca__gte=80)

    escopo_classes = Predicao.objects.all() if request.user.is_staff else Predicao.objects.filter(captura__usuario=request.user)

    consulta = request.GET.copy()

    consulta.pop("page", None)

    contexto = {
        # O filtro por alertas pode repetir a mesma predição.
        "pagina": Paginator(predicoes.distinct(), 15).get_page(request.GET.get("page")),
        "classes": escopo_classes.values_list("classe_prevista", flat=True).distinct().order_by("classe_prevista"),
        "usuarios": get_user_model().objects.order_by("first_name", "email") if request.user.is_staff else (),
        "parametros_consulta": consulta.urlencode(),
    }

    return render(request, "predictions/history.html", contexto)
