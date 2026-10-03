from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
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
    """
    Função utilitária interna para manipular a query string da requisição.
    Copia os parâmetros GET da URL atual e remove o parâmetro 'page', permitindo que
    os links de paginação no HTML preservem os filtros aplicados (pesquisa, datas, etc.).
    """
    consulta = request.GET.copy()
    consulta.pop("page", None)
    return consulta.urlencode()


@login_required
def listar_capturas(request):
    """
    View responsável por listar e filtrar as capturas com paginação.
    Administradores (staff) visualizam capturas de todos os usuários, enquanto usuários
    comuns acessam apenas seus próprios registros.
    """
    # Define o escopo base conforme o nível de permissão do usuário
    capturas = Captura.objects.all() if request.user.is_staff else request.user.capturas.all()

    # Otimização ORM: previne o problema N+1 ao carregar antecipadamente os relacionamentos
    capturas = capturas.select_related("leitura_ambiental", "predicao", "usuario")

    # Aplicação dinâmica de filtros baseados nos parâmetros GET fornecidos na URL
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
    """
    View responsável pelo cadastro manual de novas capturas e suas leituras
    ambientais associadas via formulário web.
    """
    formulario = FormularioCaptura(request.POST or None, request.FILES or None)

    if request.method == "POST" and formulario.is_valid():
        captura = formulario.save(commit=False)
        captura.usuario = request.user
        captura.save()

        # Dispara a criação/geração do registro de leitura ambiental (temperatura e umidade)
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
    """
    View de detalhamento de uma captura específica. Respeita o isolamento por usuário
    a menos que este seja membro da equipe (is_staff).
    """
    capturas = Captura.objects.all() if request.user.is_staff else request.user.capturas.all()

    captura = get_object_or_404(
        capturas.select_related("leitura_ambiental", "predicao", "usuario"),
        pk=id_captura,
    )

    return render(request, "captures/detail.html", {"captura": captura})


@login_required
@require_POST
def processar_captura_existente(request, id_captura):
    """
    View acionada via POST para solicitar o processamento/análise do modelo de IA
    sobre uma captura existente. Trata retornos de exceção e insere mensagens de feedback para a interface.
    """
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

    # Notifica o usuário caso a segmentação via MobileSAM tenha falhado e caído em fallback
    if predicao.status_preprocessamento == predicao.StatusPreprocessamento.FALLBACK_ROI:
        messages.warning(
            request,
            "O MobileSAM não encontrou uma segmentação segura. A análise usou o recorte central.",
        )

    return redirect("detalhar_captura", id_captura=predicao.captura_id)