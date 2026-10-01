from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .models import Alerta


@login_required
def listar_alertas(request):
    alertas = Alerta.objects.all() if request.user.is_staff else Alerta.objects.filter(captura__usuario=request.user)

    alertas = alertas.select_related("captura", "captura__usuario", "predicao")

    if request.GET.get("q"):
        alertas = alertas.filter(
            Q(mensagem__icontains=request.GET["q"]) |
            Q(captura__observacao__icontains=request.GET["q"])
        )

    if request.GET.get("date_from"):
        alertas = alertas.filter(criado_em__date__gte=request.GET["date_from"])

    if request.GET.get("date_to"):
        alertas = alertas.filter(criado_em__date__lte=request.GET["date_to"])

    if request.GET.get("type"):
        alertas = alertas.filter(tipo=request.GET["type"])

    if request.GET.get("severity"):
        alertas = alertas.filter(severidade=request.GET["severity"])

    if request.GET.get("viewed") in ("0", "1"):
        alertas = alertas.filter(visualizado=request.GET["viewed"] == "1")

    if request.user.is_staff and request.GET.get("user"):
        alertas = alertas.filter(captura__usuario_id=request.GET["user"])

    consulta = request.GET.copy()

    consulta.pop("page", None)

    return render(request, "alerts/list.html", {
        "pagina": Paginator(alertas, 15).get_page(request.GET.get("page")),
        "tipos": Alerta.Tipo.choices,
        "severidades": Alerta.Severidade.choices,
        "usuarios": get_user_model().objects.order_by("first_name", "email") if request.user.is_staff else (),
        "parametros_consulta": consulta.urlencode(),
    })


@login_required
@require_POST
def marcar_como_visualizado(request, id_alerta):
    alertas = Alerta.objects.all() if request.user.is_staff else Alerta.objects.filter(captura__usuario=request.user)

    alerta = get_object_or_404(alertas, pk=id_alerta)

    alerta.visualizado = True

    alerta.save(update_fields=["visualizado"])

    messages.success(request, "Alerta marcado como visualizado.")

    return redirect("lista_alertas")
