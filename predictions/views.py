from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.core.paginator import Paginator
from django.shortcuts import render
from .models import Prediction


@login_required
def history(request):
    """
    View responsável por listar o histórico de predições.
    Inclui regras de isolamento de dados por perfil de usuário, otimização de consultas ao banco,
    aplicação de múltiplos filtros combinados e paginação de resultados.
    """
    
    # Define o escopo base de visibilidade: 
    # Administradores (staff) veem todas as predições; usuários comuns veem apenas as suas.
    predictions = Prediction.objects.all() if request.user.is_staff else Prediction.objects.filter(capture__user=request.user)
    
    # Otimização de banco de dados (evita o problema de N+1 queries)
    # Traz os dados da captura e do usuário na mesma query, e carrega os alertas em uma query separada.
    predictions = predictions.select_related("capture", "capture__user").prefetch_related("alerts")
    
    # Filtro de busca textual em múltiplos campos (classe prevista ou observação da captura)
    if request.GET.get("q"):
        predictions = predictions.filter(
            Q(predicted_class__icontains=request.GET["q"]) | 
            Q(capture__observation__icontains=request.GET["q"])
        )
        
    # Filtro exclusivo para administradores buscarem predições de um usuário específico
    if request.user.is_staff and request.GET.get("user"):
        predictions = predictions.filter(capture__user_id=request.GET["user"])
        
    # Filtros por intervalo de datas
    if request.GET.get("date_from"):
        predictions = predictions.filter(predicted_at__date__gte=request.GET["date_from"])
    if request.GET.get("date_to"):
        predictions = predictions.filter(predicted_at__date__lte=request.GET["date_to"])
        
    # Filtro por correspondência exata de classe prevista
    if request.GET.get("class"):
        predictions = predictions.filter(predicted_class=request.GET["class"])
        
    # Filtro por severidade do alerta associado
    if request.GET.get("severity"):
        predictions = predictions.filter(alerts__severity=request.GET["severity"])
        
    # Filtro por faixas de porcentagem de confiança do modelo
    if request.GET.get("confidence") == "low":
        predictions = predictions.filter(confidence__lt=60)
    elif request.GET.get("confidence") == "medium":
        predictions = predictions.filter(confidence__gte=60, confidence__lt=80)
    elif request.GET.get("confidence") == "high":
        predictions = predictions.filter(confidence__gte=80)
        
    # Define o escopo de classes que aparecerão no filtro suspenso (dropdown) 
    # garantindo que o usuário veja apenas as classes presentes em seus próprios dados.
    class_scope = Prediction.objects.all() if request.user.is_staff else Prediction.objects.filter(capture__user=request.user)
    
    # Preserva os parâmetros da URL (filtros) para repassá-los aos botões de paginação,
    # removendo apenas o número da página atual.
    query = request.GET.copy()
    query.pop("page", None)
    
    # Monta o contexto para renderização do template
    context = {
        # Paginação: limita a 15 resultados por página. 
        # O .distinct() é necessário para evitar registros duplicados causados pelos filtros em tabelas relacionadas (alerts).
        "page_obj": Paginator(predictions.distinct(), 15).get_page(request.GET.get("page")),
        
        # Lista única de classes ordenadas alfabeticamente para povoar o menu de filtros
        "classes": class_scope.values_list("predicted_class", flat=True).distinct().order_by("predicted_class"),
        
        # Lista de usuários (apenas para equipe administrativa) para o filtro de usuários
        "users": get_user_model().objects.order_by("first_name", "email") if request.user.is_staff else (),
        
        # String de parâmetros formatada para ser usada nos links numéricos da paginação
        "querystring": query.urlencode(),
    }
    
    return render(request, "predictions/history.html", context)