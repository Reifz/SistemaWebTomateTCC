from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .models import Alert


@login_required
def alert_list(request):
    """
    View responsável por listar e filtrar os alertas do sistema.
    Aplica escopo de visibilidade por perfil de usuário (Staff vê todos, comum vê apenas os próprios),
    otimização de consultas ORM e suporte a paginação mantendo parâmetros da URL.
    """
    # Define a visibilidade inicial: equipe/staff visualiza todos os alertas; usuários comuns veem apenas os vinculados às suas capturas
    alerts = Alert.objects.all() if request.user.is_staff else Alert.objects.filter(capture__user=request.user)
    
    # Otimização do banco de dados (evita problema N+1 queries):
    # Executa JOIN antecipado para trazer dados da captura, usuário e predição na mesma consulta SQL
    alerts = alerts.select_related("capture", "capture__user", "prediction")
    
    # Filtro de busca textual abrangendo mensagem do alerta ou observação da captura relacionada
    if request.GET.get("q"):
        alerts = alerts.filter(
            Q(message__icontains=request.GET["q"]) | 
            Q(capture__observation__icontains=request.GET["q"])
        )
        
    # Filtros por intervalo de datas de criação do alerta
    if request.GET.get("date_from"):
        alerts = alerts.filter(created_at__date__gte=request.GET["date_from"])
    if request.GET.get("date_to"):
        alerts = alerts.filter(created_at__date__lte=request.GET["date_to"])
        
    # Filtro por tipo de alerta (ex: Fitossanitário, Ambiental, Crítico)
    if request.GET.get("type"):
        alerts = alerts.filter(type=request.GET["type"])
        
    # Filtro por nível de severidade (ex: Baixa, Média, Alta, Crítica)
    if request.GET.get("severity"):
        alerts = alerts.filter(severity=request.GET["severity"])
        
    # Filtro por status de visualização/leitura ("1" para lidos, "0" para não lidos)
    if request.GET.get("viewed") in ("0", "1"):
        alerts = alerts.filter(viewed=request.GET["viewed"] == "1")
        
    # Filtro exclusivo para administradores filtrarem alertas de um usuário específico
    if request.user.is_staff and request.GET.get("user"):
        alerts = alerts.filter(capture__user_id=request.GET["user"])
        
    # Preserva os parâmetros de filtro ativos na URL para não perder o contexto ao trocar de página na paginação
    query = request.GET.copy()
    query.pop("page", None)
    
    return render(request, "alerts/list.html", {
        # Paginação: limita a exibição a 15 alertas por página
        "page_obj": Paginator(alerts, 15).get_page(request.GET.get("page")),
        "types": Alert.Type.choices,
        "severities": Alert.Severity.choices,
        # Carrega a lista de usuários para o dropdown apenas se for staff
        "users": get_user_model().objects.order_by("first_name", "email") if request.user.is_staff else (),
        "querystring": query.urlencode(),
    })


@login_required
@require_POST
def mark_read(request, pk):
    """
    View de ação para marcar um alerta como visualizado/lido.
    Restrita ao método POST para prevenção de alterações acidentais via navegação GET.
    """
    # Garante o isolamento de dados ao buscar o alerta de acordo com o perfil do usuário
    alerts = Alert.objects.all() if request.user.is_staff else Alert.objects.filter(capture__user=request.user)
    alert = get_object_or_404(alerts, pk=pk)
    
    # Atualiza a flag de visualização e utiliza update_fields para otimizar a instrução UPDATE no SQL
    alert.viewed = True
    alert.save(update_fields=["viewed"])
    
    messages.success(request, "Alerta marcado como visualizado.")
    return redirect("alert_list")