from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from predictions.services import gerar_leitura_ambiental, processar_captura
from .forms import FormularioCaptura
from .models import Capture


def _consulta_sem_pagina(request):
    """
    Função auxiliar que limpa o parâmetro 'page' dos parâmetros da URL (QueryDict).
    Mantém os filtros ativos ao navegar entre as páginas de resultado na paginação.
    """
    consulta = request.GET.copy()
    consulta.pop("page", None)
    return consulta.urlencode()


@login_required
def capture_list(request):
    """
    View responsável pela listagem e filtragem das capturas cadastradas.
    Aplica escopo de visibilidade por perfil (Staff vs. Usuário comum) e paginação.
    """
    # Define a visibilidade inicial: administradores veem todas, usuários comuns veem apenas as suas
    captures = Capture.objects.all() if request.user.is_staff else request.user.captures.all()
    
    # Otimiza o acesso ao banco evitando N+1 queries ao carregar relacionamentos chave na mesma consulta
    captures = captures.select_related("environmental_reading", "prediction", "user")
    
    # Aplicação de filtros dinâmicos via parâmetros da URL (GET)
    if request.GET.get("q"):
        captures = captures.filter(observation__icontains=request.GET["q"])
    if request.GET.get("date_from"):
        captures = captures.filter(captured_at__date__gte=request.GET["date_from"])
    if request.GET.get("date_to"):
        captures = captures.filter(captured_at__date__lte=request.GET["date_to"])
    if request.GET.get("origin"):
        captures = captures.filter(origin=request.GET["origin"])
    if request.GET.get("status"):
        captures = captures.filter(status=request.GET["status"])
    if request.user.is_staff and request.GET.get("user"):
        captures = captures.filter(user_id=request.GET["user"])
        
    return render(request, "captures/list.html", {
        "page_obj": Paginator(captures, 15).get_page(request.GET.get("page")),
        "querystring": _consulta_sem_pagina(request),
        "origins": (("manual", "Manual"), ("simulado", "Sistema"), ("esp32", "Dispositivo")),
        "statuses": Capture.Status.choices,
        "users": get_user_model().objects.order_by("first_name", "email") if request.user.is_staff else (),
    })


@login_required
def capture_create(request):
    """
    View para cadastro de novas capturas e registro automático de leitura ambiental.
    Garante o vínculo automático da captura com o usuário logado.
    """
    form = FormularioCaptura(request.POST or None, request.FILES or None)
    
    if request.method == "POST" and form.is_valid():
        capture = form.save(commit=False)
        capture.user = request.user
        capture.save()  # Ponto de integração futura: persiste imagens enviadas via ESP32.
        
        # Gera a leitura de temperatura e umidade associada à captura recém-salva
        gerar_leitura_ambiental(
            capture, 
            form.cleaned_data.get("temperature"), 
            form.cleaned_data.get("humidity")
        )
        
        messages.success(request, "Captura cadastrada com leitura ambiental.")
        return redirect("capture_detail", pk=capture.pk)
        
    return render(request, "captures/form.html", {"form": form})


@login_required
def capture_detail(request, pk):
    """
    View de detalhamento de uma captura específica.
    Garante que usuários comuns só consigam visualizar detalhes de suas próprias capturas.
    """
    captures = Capture.objects.all() if request.user.is_staff else request.user.captures.all()
    capture = get_object_or_404(
        captures.select_related("environmental_reading", "prediction", "user"), 
        pk=pk
    )
    return render(request, "captures/detail.html", {"capture": capture})


@login_required
@require_POST
def capture_process(request, pk):
    """
    View para acionar a análise de IA/processamento em uma captura existente.
    Restrita a requisições POST para evitar acionamento acidental via navegação GET.
    """
    captures = Capture.objects.all() if request.user.is_staff else request.user.captures.all()
    capture = get_object_or_404(captures, pk=pk)
    
    # Processa a inferência e retorna se uma nova predição foi criada ou reaproveitada
    predicao, criada = processar_captura(capture)
    
    # Notifica o usuário de acordo com o resultado do processamento
    messages.success(
        request, 
        "Análise concluída." if criada else "Esta captura já havia sido analisada."
    )
    return redirect("capture_detail", pk=predicao.capture_id)