from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import FormularioDispositivo
from .models import Dispositivo


@staff_member_required
def listar_dispositivos(request):
    dispositivos = Dispositivo.objects.select_related("usuario")

    if request.GET.get("q"):
        termo_busca = request.GET["q"]
        dispositivos = dispositivos.filter(
            Q(identificador__icontains=termo_busca)
            | Q(nome__icontains=termo_busca)
            | Q(localizacao__icontains=termo_busca)
            | Q(usuario__email__icontains=termo_busca)
        )

    if request.GET.get("status") in (Dispositivo.Status.ATIVO, Dispositivo.Status.INATIVO):
        dispositivos = dispositivos.filter(status=request.GET["status"])

    parametros_consulta = request.GET.copy()
    parametros_consulta.pop("page", None)

    contexto = {
        "pagina": Paginator(dispositivos, 20).get_page(request.GET.get("page")),
        "status_dispositivos": Dispositivo.Status.choices,
        "parametros_consulta": parametros_consulta.urlencode(),
    }

    return render(
        request,
        "devices/list.html",
        contexto,
    )


@staff_member_required
def criar_dispositivo(request):
    formulario = FormularioDispositivo(request.POST or None)

    if request.method == "POST" and formulario.is_valid():
        formulario.save()
        messages.success(request, "Dispositivo cadastrado com sucesso.")
        return redirect("lista_dispositivos")

    return render(request, "devices/form.html", {"formulario": formulario, "titulo": "Novo dispositivo"})


@staff_member_required
def editar_dispositivo(request, id_dispositivo):
    dispositivo = get_object_or_404(Dispositivo, pk=id_dispositivo)
    formulario = FormularioDispositivo(request.POST or None, instance=dispositivo)

    if request.method == "POST" and formulario.is_valid():
        formulario.save()
        messages.success(request, "Dispositivo atualizado com sucesso.")
        return redirect("lista_dispositivos")

    return render(
        request,
        "devices/form.html",
        {"formulario": formulario, "titulo": "Editar dispositivo", "dispositivo": dispositivo},
    )
