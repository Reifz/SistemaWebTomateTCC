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

# Obtém dinamicamente o model de usuário ativo no projeto (customizado ou padrão do Django)
Usuario = get_user_model()


@staff_member_required
def listar_usuarios(request):
    """
    Exibe a lista paginada de usuários do sistema.
    Permite busca por texto (nome/e-mail) e filtros por papel (admin/user) e status (ativo/inativo).
    Acesso restrito a membros da equipe (staff).
    """
    # Consulta inicial ordenando por nome, sobrenome e e-mail
    usuarios = Usuario.objects.order_by("first_name", "last_name", "email")

    # Filtro de busca por termo nos campos de nome, sobrenome ou e-mail (case-insensitive)
    if request.GET.get("q"):
        termo_busca = request.GET["q"]
        usuarios = usuarios.filter(
            Q(first_name__icontains=termo_busca) |
            Q(last_name__icontains=termo_busca) |
            Q(email__icontains=termo_busca)
        )

    # Filtro por tipo de usuário (Administrador vs Usuário Padrão)
    if request.GET.get("role") == "admin":
        usuarios = usuarios.filter(is_staff=True)
    elif request.GET.get("role") == "user":
        usuarios = usuarios.filter(is_staff=False)

    # Filtro por status da conta (Ativo vs Inativo)
    if request.GET.get("status") in ("active", "inactive"):
        usuarios = usuarios.filter(is_active=request.GET["status"] == "active")

    # Preserva os parâmetros da URL para manter os filtros ativos na navegação da paginação
    consulta = request.GET.copy()
    consulta.pop("page", None)

    return render(
        request,
        "accounts/list.html",
        {
            # Pagina os resultados exibindo 15 usuários por página
            "pagina": Paginator(usuarios, 15).get_page(request.GET.get("page")),
            "parametros_consulta": consulta.urlencode(),
        }
    )


@staff_member_required
def criar_usuario(request):
    """
    Exibe e processa o formulário para cadastro de novos usuários no sistema.
    Acesso restrito a membros da equipe (staff).
    """
    formulario = FormularioCriacaoUsuario(request.POST or None)

    if request.method == "POST" and formulario.is_valid():
        formulario.save()
        messages.success(request, "Usuário criado com sucesso.")
        return redirect("lista_usuarios")

    return render(
        request,
        "accounts/form.html",
        {"formulario": formulario, "titulo": "Novo usuário"},
    )


@staff_member_required
def editar_usuario(request, id_usuario):
    """
    Edita os dados de um usuário específico a partir do seu ID (PK).
    Acesso restrito a membros da equipe (staff).
    """
    # Busca o usuário pelo ID ou retorna erro 404 caso não seja encontrado
    conta = get_object_or_404(Usuario, pk=id_usuario)

    formulario = FormularioEdicaoUsuario(
        request.POST or None,
        instance=conta,
        usuario_logado=request.user
    )

    if request.method == "POST" and formulario.is_valid():
        formulario.save()
        messages.success(request, "Usuário atualizado com sucesso.")
        return redirect("lista_usuarios")

    return render(
        request,
        "accounts/form.html",
        {"formulario": formulario, "titulo": "Editar usuário", "conta": conta},
    )


@login_required
def perfil(request):
    """
    Permite ao usuário autenticado visualizar e alterar suas próprias informações de perfil e senha.
    Acessível por qualquer usuário logado.
    """
    formulario = FormularioPerfil(request.POST or None, instance=request.user)

    if request.method == "POST" and formulario.is_valid():
        usuario = formulario.save()

        # Mantém a sessão do usuário ativa caso ele tenha atualizado sua senha
        if formulario.cleaned_data.get("nova_senha"):
            update_session_auth_hash(request, usuario)

        messages.success(request, "Perfil atualizado com sucesso.")
        return redirect("perfil")

    return render(request, "accounts/profile.html", {"formulario": formulario})


@staff_member_required
@require_POST
def inserir_dados(request):
    """
    Gera e insere dados demonstrativos/fictícios para todos os usuários ativos do sistema.
    Ação restrita a POST e membros da equipe (staff).
    """
    usuarios = Usuario.objects.filter(is_active=True).order_by("pk")

    # Executa a regra de negócio importada do módulo de serviços
    resultado = inserir_dados_demonstrativos(usuarios)

    messages.success(
        request,
        f"{resultado['capturas']} capturas demonstrativas inseridas para {resultado['usuarios']} usuário(s).",
    )

    # Captura a URL de retorno informada no formulário
    destino = request.POST.get("next")

    # Proteção contra ataques de Open Redirect: garante que o destino seja do mesmo domínio
    if not destino or not url_has_allowed_host_and_scheme(
        destino,
        allowed_hosts={request.get_host()}
    ):
        destino = "inicio"

    return redirect(destino)


@staff_member_required
@require_POST
def truncar_dados(request):
    """
    Remove todos os dados operacionais (capturas, leituras, previsões e alertas) do banco.
    Ação destrutiva restrita a chamadas via POST por membros da equipe (staff).
    """
    # Executa a limpeza via serviço especializado
    totais = truncar_dados_operacionais()

    messages.success(
        request,
        f"Dados removidos: {totais['capturas']} capturas, {totais['leituras']} leituras, "
        f"{totais['previsoes']} previsões e {totais['alertas']} alertas.",
    )

    return redirect("inicio")