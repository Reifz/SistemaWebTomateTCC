from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import FileResponse, Http404
from django.shortcuts import render
from alerts.models import Alerta
from captures.models import Captura
from .services import resumo_painel


def _usuario_selecionado(request):
    if not request.user.is_staff or not request.GET.get("user"):
        return None

    return get_user_model().objects.filter(pk=request.GET["user"]).first()


@login_required
def inicio(request):
    usuario_selecionado = _usuario_selecionado(request)

    contexto = resumo_painel(request.user, usuario_selecionado)

    capturas = request.user.capturas.all() if not request.user.is_staff else Captura.objects.all()

    alertas = Alerta.objects.filter(captura__in=capturas)

    contexto.update({
        "ultimas_capturas": capturas.select_related("predicao")[:5],
        "ultimos_alertas": alertas[:5],
    })

    return render(request, "dashboard/home.html", contexto)


@login_required
def painel(request):
    usuario_selecionado = _usuario_selecionado(request)

    contexto = resumo_painel(request.user, usuario_selecionado)

    capturas = request.user.capturas.all() if not request.user.is_staff else Captura.objects.all()

    if usuario_selecionado:
        capturas = capturas.filter(usuario=usuario_selecionado)

    contexto.update({
        "ultimas_capturas": capturas.select_related("predicao")[:5],
        "ultimos_alertas": Alerta.objects.filter(captura__in=capturas)[:5],
        "usuarios": get_user_model().objects.order_by("first_name", "email") if request.user.is_staff else (),
        "usuario_selecionado": usuario_selecionado,
    })

    return render(request, "dashboard/index.html", contexto)


@login_required
def imagem_resultado_manual(request, id_execucao, tipo_imagem):
    """Entrega uma imagem de resultado sem permitir acesso fora da pasta configurada."""

    nomes_arquivos = {
        "original": ("imagem_original.jpeg", "image/jpeg"),
        "processed": ("preprocessamento/imagem_processada.jpg", "image/jpeg"),
        "guide": ("preprocessamento/imagem_com_guia.jpg", "image/jpeg"),
    }

    if tipo_imagem not in nomes_arquivos:
        raise Http404

    raiz = Path(settings.RESULTS_ROOT).resolve()

    caminho_imagem = (raiz / id_execucao / nomes_arquivos[tipo_imagem][0]).resolve()

    if raiz not in caminho_imagem.parents or not caminho_imagem.is_file():
        raise Http404

    return FileResponse(caminho_imagem.open("rb"), content_type=nomes_arquivos[tipo_imagem][1])
