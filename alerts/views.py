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
    """
    Exibe a listagem paginada de alertas do sistema.
    Permite busca por texto, filtro por intervalo de datas, tipo, severidade, 
    status de leitura e usuário proprietário (exclusivo para staff).
    Acessível por qualquer usuário autenticado.
    """
    # Controle de acesso multitenant: staff visualiza tudo; usuário comum vê apenas seus próprios alertas
    alertas = Alerta.objects.all() if request.user.is_staff else Alerta.objects.filter(captura__usuario=request.user)

    # Otimização de performance (Eager Loading) para evitar o problema N+1 em relacionamentos ForeignKey
    alertas = alertas.select_related("captura", "captura__usuario", "predicao")

    # Filtro de busca por texto parcial na mensagem do alerta ou observação da captura
    if request.GET.get("q"):
        alertas = alertas.filter(
            Q(mensagem__icontains=request.GET["q"]) |
            Q(captura__observacao__icontains=request.GET["q"])
        )

    # Filtros por intervalo de datas de criação (data inicial e data final)
    if request.GET.get("date_from"):
        alertas = alertas.filter(criado_em__date__gte=request.GET["date_from"])

    if request.GET.get("date_to"):
        alertas = alertas.filter(criado_em__date__lte=request.GET["date_to"])

    # Filtro por tipo de alerta (ex: CRITICO, FITOSSANITARIO, etc.)
    if request.GET.get("type"):
        alertas = alertas.filter(tipo=request.GET["type"])

    # Filtro por nível de severidade (ex: ALTA, MEDIA, etc.)
    if request.GET.get("severity"):
        alertas = alertas.filter(severidade=request.GET["severity"])

    # Filtro por status de leitura ("1" para visualizados, "0" para não visualizados)
    if request.GET.get("viewed") in ("0", "1"):
        alertas = alertas.filter(visualizado=request.GET["viewed"] == "1")

    # Filtro por ID do usuário (disponível somente para membros da equipe/staff)
    if request.user.is_staff and request.GET.get("user"):
        alertas = alertas.filter(captura__usuario_id=request.GET["user"])

    # Copia os parâmetros de URL e remove a chave 'page' para manter os filtros ativos na paginação
    consulta = request.GET.copy()
    consulta.pop("page", None)

    return render(request, "alerts/list.html", {
        # Pagina os registros de alertas em blocos de 15 por página
        "pagina": Paginator(alertas, 15).get_page(request.GET.get("page")),
        "tipos": Alerta.Tipo.choices,
        "severidades": Alerta.Severidade.choices,
        # Carrega a lista de usuários para seleção no filtro caso o usuário seja staff
        "usuarios": get_user_model().objects.order_by("first_name", "email") if request.user.is_staff else (),
        "parametros_consulta": consulta.urlencode(),
    })


@login_required
@require_POST
def marcar_como_visualizado(request, id_alerta):
    """
    Marca um alerta específico como lido/visualizado no banco de dados.
    Ação restrita a requisições HTTP POST e usuários autenticados com permissão de acesso ao alerta.
    """
    # Garante o controle de acesso: recupera a base de alertas de acordo com a permissão do usuário
    alertas = Alerta.objects.all() if request.user.is_staff else Alerta.objects.filter(captura__usuario=request.user)

    # Busca o alerta pelo ID ou lança erro 404 (caso não exista ou o usuário não tenha permissão de acesso)
    alerta = get_object_or_404(alertas, pk=id_alerta)

    # Altera o estado do campo
    alerta.visualizado = True

    # Salva apenas o campo modificado no banco de dados para otimizar a instrução UPDATE
    alerta.save(update_fields=["visualizado"])

    messages.success(request, "Alerta marcado como visualizado.")

    return redirect("lista_alertas")