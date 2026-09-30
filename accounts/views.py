from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme

from captures.services import inserir_dados_demonstrativos, truncar_dados_operacionais
from .forms import FormularioCriacaoUsuario, FormularioEdicaoUsuario, FormularioPerfil

Usuario = get_user_model()


@staff_member_required
def user_list(request):
    """
    View administrativa de listagem e filtragem de usuários.
    Restrita a membros da equipe (`is_staff=True`), com suporte a paginação 
    e preservação dos parâmetros de busca na URL.
    """
    users = Usuario.objects.order_by("first_name", "last_name", "email")
    
    # Filtro de busca textual por nome, sobrenome ou e-mail
    if request.GET.get("q"):
        q = request.GET["q"]
        users = users.filter(
            Q(first_name__icontains=q) | 
            Q(last_name__icontains=q) | 
            Q(email__icontains=q)
        )
        
    # Filtro por tipo de permissão (Administrador vs. Usuário padrão)
    if request.GET.get("role") == "admin":
        users = users.filter(is_staff=True)
    elif request.GET.get("role") == "user":
        users = users.filter(is_staff=False)
        
    # Filtro por status de atividade da conta
    if request.GET.get("status") in ("active", "inactive"):
        users = users.filter(is_active=request.GET["status"] == "active")
        
    # Preserva os parâmetros de consulta ao navegar pelas páginas
    query = request.GET.copy()
    query.pop("page", None)
    
    return render(
        request, 
        "accounts/list.html", 
        {
            "page_obj": Paginator(users, 15).get_page(request.GET.get("page")), 
            "querystring": query.urlencode()
        }
    )


@staff_member_required
def user_create(request):
    """View administrativa para cadastro de novos usuários no sistema."""
    form = FormularioCriacaoUsuario(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Usuário criado com sucesso.")
        return redirect("user_list")
        
    return render(
        request, 
        "accounts/form.html", 
        {"form": form, "heading": "Novo usuário"}
    )


@staff_member_required
def user_edit(request, pk):
    """View administrativa para edição dos dados e permissões de um usuário existente."""
    account = get_object_or_404(Usuario, pk=pk)
    form = FormularioEdicaoUsuario(
        request.POST or None, 
        instance=account, 
        usuario_logado=request.user
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Usuário atualizado com sucesso.")
        return redirect("user_list")
        
    return render(
        request, 
        "accounts/form.html", 
        {"form": form, "heading": "Editar usuário", "account": account}
    )


@login_required
def perfil(request):
    """
    View de autoatendimento para o usuário atualizar suas próprias informações pessoais.
    Usa `update_session_auth_hash` caso a senha seja alterada para evitar o logout automático.
    """
    form = FormularioPerfil(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        usuario = form.save()
        
        # Mantém a sessão do usuário ativa mesmo após modificar a senha de acesso
        if form.cleaned_data.get("nova_senha"):
            update_session_auth_hash(request, usuario)
            
        messages.success(request, "Perfil atualizado com sucesso.")
        return redirect("perfil")
        
    return render(request, "accounts/profile.html", {"form": form})


@staff_member_required
@require_POST
def inserir_dados(request):
    """
    View administrativa de ação para popular o banco de dados com amostras demonstrativas.
    Valida a URL de retorno (`next`) contra ataques de Open Redirect antes de redirecionar.
    """
    usuarios = Usuario.objects.filter(is_active=True).order_by("pk")
    resultado = inserir_dados_demonstrativos(usuarios)
    
    messages.success(
        request,
        f"{resultado['capturas']} capturas demonstrativas inseridas para {resultado['usuarios']} usuário(s).",
    )
    
    # Sanitização da URL de destino contra invasões via Open Redirect
    destino = request.POST.get("next")
    if not destino or not url_has_allowed_host_and_scheme(
        destino, 
        allowed_hosts={request.get_host()}
    ):
        destino = "home"
        
    return redirect(destino)


@staff_member_required
@require_POST
def truncar_dados(request):
    """
    View administrativa de ação para realizar a limpeza (zerar) de dados operacionais
    (capturas, leituras de sensores, predições e alertas), mantendo o histórico limpo.
    """
    totais = truncar_dados_operacionais()
    messages.success(
        request,
        f"Dados removidos: {totais['capturas']} capturas, {totais['leituras']} leituras, "
        f"{totais['previsoes']} previsões e {totais['alertas']} alertas.",
    )
    return redirect("home")