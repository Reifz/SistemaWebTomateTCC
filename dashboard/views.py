from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import FileResponse, Http404
from django.shortcuts import render
from alerts.models import Alert
from captures.models import Capture
from .services import resumo_dashboard

def _usuario_selecionado(request):
    if not request.user.is_staff or not request.GET.get("user"):
        return None
    return get_user_model().objects.filter(pk=request.GET["user"]).first()


@login_required
def inicio(request):
    usuario_selecionado = _usuario_selecionado(request)

    contexto = resumo_dashboard(request.user, usuario_selecionado)
    capturas = request.user.captures.all() if not request.user.is_staff else Capture.objects.all()
    alertas = Alert.objects.filter(capture__in=capturas)
    contexto.update({
        "latest_captures": capturas.select_related("prediction")[:5],
        "latest_alerts": alertas[:5],
    })
    return render(request, "dashboard/home.html", contexto)


@login_required
def painel(request):
    usuario_selecionado = _usuario_selecionado(request)
    contexto = resumo_dashboard(request.user, usuario_selecionado)
    capturas = request.user.captures.all() if not request.user.is_staff else Capture.objects.all()
    if usuario_selecionado:
        capturas = capturas.filter(user=usuario_selecionado)
    contexto.update({
        "latest_captures": capturas.select_related("prediction")[:5],
        "latest_alerts": Alert.objects.filter(capture__in=capturas)[:5],
        "users": get_user_model().objects.order_by("first_name", "email") if request.user.is_staff else (),
        "selected_user": usuario_selecionado,
    })
    return render(request, "dashboard/index.html", contexto)


@login_required
def imagem_resultado_manual(request, run_id, image_type):
    nomes_arquivos = {
        "original": ("imagem_original.jpeg", "image/jpeg"),
        "processed": ("preprocessamento/imagem_processada.jpg", "image/jpeg"),
        "guide": ("preprocessamento/imagem_com_guia.jpg", "image/jpeg"),
    }
    if image_type not in nomes_arquivos:
        raise Http404

    raiz = Path(settings.RESULTS_ROOT).resolve()
    caminho_imagem = (raiz / run_id / nomes_arquivos[image_type][0]).resolve()
    if raiz not in caminho_imagem.parents or not caminho_imagem.is_file():
        raise Http404
    return FileResponse(caminho_imagem.open("rb"), content_type=nomes_arquivos[image_type][1])
