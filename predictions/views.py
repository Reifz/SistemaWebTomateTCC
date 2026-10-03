from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from .models import Predicao


@login_required
def historico(request):
    """
    Exibe o histórico paginado de predições com suporte a filtros dinâmicos de busca,
    período, classe, severidade de alertas, nível de confiança e usuário (para staff).
    """
    # Restringe o escopo inicial com base no nível de permissão do usuário
    if request.user.is_staff:
        predicoes = Predicao.objects.all()
    else:
        predicoes = Predicao.objects.filter(captura__usuario=request.user)

    # Otimiza o carregamento das relações de chaves estrangeiras e relacionamentos M2M
    predicoes = predicoes.select_related("captura", "captura__usuario").prefetch_related("alertas")

    # Filtro de busca textual (classe prevista ou observação da captura)
    termo_busca = request.GET.get("q")
    if termo_busca:
        predicoes = predicoes.filter(
            Q(classe_prevista__icontains=termo_busca) | Q(captura__observacao__icontains=termo_busca)
        )

    # Filtro por usuário específico (visível apenas para superusuários/staff)
    usuario_id = request.GET.get("user")
    if request.user.is_staff and usuario_id:
        predicoes = predicoes.filter(captura__usuario_id=usuario_id)

    # Filtros por intervalo de datas
    data_inicio = request.GET.get("date_from")
    if data_inicio:
        predicoes = predicoes.filter(prevista_em__date__gte=data_inicio)

    data_fim = request.GET.get("date_to")
    if data_fim:
        predicoes = predicoes.filter(prevista_em__date__lte=data_fim)

    # Filtro por classe predita específica
    classe_selecionada = request.GET.get("class")
    if classe_selecionada:
        predicoes = predicoes.filter(classe_prevista=classe_selecionada)

    # Filtro por nível de severidade do alerta
    severidade = request.GET.get("severity")
    if severidade:
        predicoes = predicoes.filter(alertas__severidade=severidade)

    # Filtro por faixas de nível de confiança (%)
    nivel_confianca = request.GET.get("confidence")
    if nivel_confianca == "low":
        predicoes = predicoes.filter(confianca__lt=60)
    elif nivel_confianca == "medium":
        predicoes = predicoes.filter(confianca__gte=60, confianca__lt=80)
    elif nivel_confianca == "high":
        predicoes = predicoes.filter(confianca__gte=80)

    # Define o escopo para a listagem das opções no select de classes do filtro
    if request.user.is_staff:
        escopo_classes = Predicao.objects.all()
    else:
        escopo_classes = Predicao.objects.filter(captura__usuario=request.user)

    # Preserva os parâmetros da query string omitindo a página atual para manter os filtros durante a paginação
    consulta = request.GET.copy()
    consulta.pop("page", None)

    contexto = {
        # `.distinct()` evita duplicações decorrentes do JOIN com o modelo de alertas no prefetch
        "pagina": Paginator(predicoes.distinct(), 15).get_page(request.GET.get("page")),
        "classes": escopo_classes.values_list("classe_prevista", flat=True).distinct().order_by("classe_prevista"),
        "usuarios": get_user_model().objects.order_by("first_name", "email") if request.user.is_staff else (),
        "parametros_consulta": consulta.urlencode(),
    }

    return render(request, "predictions/history.html", contexto)