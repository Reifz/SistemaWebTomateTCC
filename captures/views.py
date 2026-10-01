from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from predictions.services import (
    ErroProcessamento,
    ProcessamentoEmAndamento,
    gerar_leitura_ambiental,
    processar_captura,
)
from .forms import FormularioCaptura
from .models import Captura


def _consulta_sem_pagina(request):
    consulta = request.GET.copy()

    consulta.pop("page", None)

    return consulta.urlencode()


@login_required
def listar_capturas(request):
    capturas = Captura.objects.all() if request.user.is_staff else request.user.capturas.all()

    capturas = capturas.select_related("leitura_ambiental", "predicao", "usuario")

    if request.GET.get("q"):
        capturas = capturas.filter(observacao__icontains=request.GET["q"])

    if request.GET.get("date_from"):
        capturas = capturas.filter(capturada_em__date__gte=request.GET["date_from"])

    if request.GET.get("date_to"):
        capturas = capturas.filter(capturada_em__date__lte=request.GET["date_to"])

    if request.GET.get("origin"):
        capturas = capturas.filter(origem=request.GET["origin"])

    if request.GET.get("status"):
        capturas = capturas.filter(status=request.GET["status"])

    if request.user.is_staff and request.GET.get("user"):
        capturas = capturas.filter(usuario_id=request.GET["user"])

    return render(request, "captures/list.html", {
        "pagina": Paginator(capturas, 15).get_page(request.GET.get("page")),
        "parametros_consulta": _consulta_sem_pagina(request),
        "origens": (("manual", "Manual"), ("simulado", "Sistema"), ("esp32", "Dispositivo")),
        "situacoes": Captura.Status.choices,
        "usuarios": get_user_model().objects.order_by("first_name", "email") if request.user.is_staff else (),
    })


@login_required
def criar_captura(request):
    formulario = FormularioCaptura(request.POST or None, request.FILES or None)

    if request.method == "POST" and formulario.is_valid():
        captura = formulario.save(commit=False)

        captura.usuario = request.user

        captura.save()

        gerar_leitura_ambiental(
            captura,
            formulario.cleaned_data.get("temperatura"),
            formulario.cleaned_data.get("umidade"),
        )

        messages.success(request, "Captura cadastrada com leitura ambiental.")

        return redirect("detalhar_captura", id_captura=captura.pk)

    return render(request, "captures/form.html", {"formulario": formulario})


@login_required
def detalhar_captura(request, id_captura):
    capturas = Captura.objects.all() if request.user.is_staff else request.user.capturas.all()

    captura = get_object_or_404(
        capturas.select_related("leitura_ambiental", "predicao", "usuario"),
        pk=id_captura,
    )

    return render(request, "captures/detail.html", {"captura": captura})


@login_required
@require_POST
def processar_captura_existente(request, id_captura):
    capturas = Captura.objects.all() if request.user.is_staff else request.user.capturas.all()

    captura = get_object_or_404(capturas, pk=id_captura)

    try:
        predicao, criada = processar_captura(captura)
    except ProcessamentoEmAndamento as erro:
        messages.warning(request, str(erro))

        return redirect("detalhar_captura", id_captura=captura.pk)
    except ErroProcessamento as erro:
        messages.error(request, str(erro))

        return redirect("detalhar_captura", id_captura=captura.pk)
    except Exception:
        messages.error(
            request,
            "Não foi possível concluir a análise. Verifique os modelos e tente novamente.",
        )

        return redirect("detalhar_captura", id_captura=captura.pk)

    messages.success(
        request,
        "Análise concluída." if criada else "Esta captura já havia sido analisada."
    )

    if predicao.status_preprocessamento == predicao.StatusPreprocessamento.FALLBACK_ROI:
        messages.warning(
            request,
            "O MobileSAM não encontrou uma segmentação segura. A análise usou o recorte central.",
        )

    return redirect("detalhar_captura", id_captura=predicao.captura_id)
