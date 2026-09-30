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
    """
    Função auxiliar interna para identificar e retornar o usuário selecionado via QueryParam.
    Permite o filtro de dados apenas se o usuário logado for da equipe (is_staff=True).
    """
    if not request.user.is_staff or not request.GET.get("user"):
        return None
    return get_user_model().objects.filter(pk=request.GET["user"]).first()


@login_required
def inicio(request):
    """
    View da página inicial do sistema.
    Exibe o resumo do painel, as 5 últimas capturas e os 5 últimos alertas.
    """
    usuario_selecionado = _usuario_selecionado(request)

    # Obtém as estatísticas gerais do dashboard
    contexto = resumo_dashboard(request.user, usuario_selecionado)
    
    # Define o escopo das capturas: usuário comum vê apenas as suas; staff vê todas
    capturas = request.user.captures.all() if not request.user.is_staff else Capture.objects.all()
    alertas = Alert.objects.filter(capture__in=capturas)
    
    # Adiciona as últimas 5 capturas e alertas ao contexto da página
    contexto.update({
        "latest_captures": capturas.select_related("prediction")[:5],
        "latest_alerts": alertas[:5],
    })
    return render(request, "dashboard/home.html", contexto)


@login_required
def painel(request):
    """
    View do painel principal (dashboard) com suporte a filtragem por usuário para administradores.
    """
    usuario_selecionado = _usuario_selecionado(request)
    contexto = resumo_dashboard(request.user, usuario_selecionado)
    
    # Define as capturas baseadas no perfil (comum ou staff)
    capturas = request.user.captures.all() if not request.user.is_staff else Capture.objects.all()
    
    # Aplica o filtro por usuário caso um administrador tenha selecionado na interface
    if usuario_selecionado:
        capturas = capturas.filter(user=usuario_selecionado)
        
    contexto.update({
        "latest_captures": capturas.select_related("prediction")[:5],
        "latest_alerts": Alert.objects.filter(capture__in=capturas)[:5],
        # Lista todos os usuários para o menu suspenso (apenas para staff)
        "users": get_user_model().objects.order_by("first_name", "email") if request.user.is_staff else (),
        "selected_user": usuario_selecionado,
    })
    return render(request, "dashboard/index.html", contexto)


@login_required
def imagem_resultado_manual(request, run_id, image_type):
    """
    View para servir imagens salvas no sistema (original, processada ou com guia)
    com validação de segurança de caminho de arquivo (prevenção contra Path Traversal).
    """
    # Mapeamento dos tipos de imagem permitidos e seus respectivos caminhos e MIME types
    nomes_arquivos = {
        "original": ("imagem_original.jpeg", "image/jpeg"),
        "processed": ("preprocessamento/imagem_processada.jpg", "image/jpeg"),
        "guide": ("preprocessamento/imagem_com_guia.jpg", "image/jpeg"),
    }
    
    # Valida se o tipo solicitado existe no dicionário
    if image_type not in nomes_arquivos:
        raise Http404

    # Resolve o caminho raiz dos resultados e o caminho completo do arquivo
    raiz = Path(settings.RESULTS_ROOT).resolve()
    caminho_imagem = (raiz / run_id / nomes_arquivos[image_type][0]).resolve()
    
    # Validação de segurança: garante que o arquivo existe e está dentro do diretório raiz
    if raiz not in caminho_imagem.parents or not caminho_imagem.is_file():
        raise Http404
        
    # Retorna o arquivo de imagem para o cliente
    return FileResponse(caminho_imagem.open("rb"), content_type=nomes_arquivos[image_type][1])