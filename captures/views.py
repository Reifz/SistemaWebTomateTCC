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
    consulta = request.GET.copy()
    consulta.pop("page", None)
    return consulta.urlencode()


@login_required
def capture_list(request):
    captures = Capture.objects.all() if request.user.is_staff else request.user.captures.all()
    captures = captures.select_related("environmental_reading", "prediction", "user")
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
    form = FormularioCaptura(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        capture = form.save(commit=False)
        capture.user = request.user
        capture.save()  # Future ESP32 integration will persist the received real image here.
        gerar_leitura_ambiental(capture, form.cleaned_data.get("temperature"), form.cleaned_data.get("humidity"))
        messages.success(request, "Captura cadastrada com leitura ambiental.")
        return redirect("capture_detail", pk=capture.pk)
    return render(request, "captures/form.html", {"form": form})


@login_required
def capture_detail(request, pk):
    captures = Capture.objects.all() if request.user.is_staff else request.user.captures.all()
    capture = get_object_or_404(captures.select_related("environmental_reading", "prediction", "user"), pk=pk)
    return render(request, "captures/detail.html", {"capture": capture})


@login_required
@require_POST
def capture_process(request, pk):
    captures = Capture.objects.all() if request.user.is_staff else request.user.captures.all()
    capture = get_object_or_404(captures, pk=pk)
    predicao, criada = processar_captura(capture)
    messages.success(request, "Análise concluída." if criada else "Esta captura já havia sido analisada.")
    return redirect("capture_detail", pk=predicao.capture_id)
