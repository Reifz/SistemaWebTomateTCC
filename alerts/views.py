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
    alerts = Alert.objects.all() if request.user.is_staff else Alert.objects.filter(capture__user=request.user)
    alerts = alerts.select_related("capture", "capture__user", "prediction")
    if request.GET.get("q"):
        alerts = alerts.filter(Q(message__icontains=request.GET["q"]) | Q(capture__observation__icontains=request.GET["q"]))
    if request.GET.get("date_from"):
        alerts = alerts.filter(created_at__date__gte=request.GET["date_from"])
    if request.GET.get("date_to"):
        alerts = alerts.filter(created_at__date__lte=request.GET["date_to"])
    if request.GET.get("type"):
        alerts = alerts.filter(type=request.GET["type"])
    if request.GET.get("severity"):
        alerts = alerts.filter(severity=request.GET["severity"])
    if request.GET.get("viewed") in ("0", "1"):
        alerts = alerts.filter(viewed=request.GET["viewed"] == "1")
    if request.user.is_staff and request.GET.get("user"):
        alerts = alerts.filter(capture__user_id=request.GET["user"])
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "alerts/list.html", {
        "page_obj": Paginator(alerts, 15).get_page(request.GET.get("page")),
        "types": Alert.Type.choices,
        "severities": Alert.Severity.choices,
        "users": get_user_model().objects.order_by("first_name", "email") if request.user.is_staff else (),
        "querystring": query.urlencode(),
    })


@login_required
@require_POST
def mark_read(request, pk):
    alerts = Alert.objects.all() if request.user.is_staff else Alert.objects.filter(capture__user=request.user)
    alert = get_object_or_404(alerts, pk=pk)
    alert.viewed = True
    alert.save(update_fields=["viewed"])
    messages.success(request, "Alerta marcado como visualizado.")
    return redirect("alert_list")
