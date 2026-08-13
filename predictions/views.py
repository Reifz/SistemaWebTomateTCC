from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.core.paginator import Paginator
from django.shortcuts import render
from .models import Prediction


@login_required
def history(request):
    predictions = Prediction.objects.all() if request.user.is_staff else Prediction.objects.filter(capture__user=request.user)
    predictions = predictions.select_related("capture", "capture__user").prefetch_related("alerts")
    if request.GET.get("q"):
        predictions = predictions.filter(Q(predicted_class__icontains=request.GET["q"]) | Q(capture__observation__icontains=request.GET["q"]))
    if request.user.is_staff and request.GET.get("user"):
        predictions = predictions.filter(capture__user_id=request.GET["user"])
    if request.GET.get("date_from"):
        predictions = predictions.filter(predicted_at__date__gte=request.GET["date_from"])
    if request.GET.get("date_to"):
        predictions = predictions.filter(predicted_at__date__lte=request.GET["date_to"])
    if request.GET.get("class"):
        predictions = predictions.filter(predicted_class=request.GET["class"])
    if request.GET.get("severity"):
        predictions = predictions.filter(alerts__severity=request.GET["severity"])
    if request.GET.get("confidence") == "low":
        predictions = predictions.filter(confidence__lt=60)
    elif request.GET.get("confidence") == "medium":
        predictions = predictions.filter(confidence__gte=60, confidence__lt=80)
    elif request.GET.get("confidence") == "high":
        predictions = predictions.filter(confidence__gte=80)
    class_scope = Prediction.objects.all() if request.user.is_staff else Prediction.objects.filter(capture__user=request.user)
    query = request.GET.copy()
    query.pop("page", None)
    context = {
        "page_obj": Paginator(predictions.distinct(), 15).get_page(request.GET.get("page")),
        "classes": class_scope.values_list("predicted_class", flat=True).distinct().order_by("predicted_class"),
        "users": get_user_model().objects.order_by("first_name", "email") if request.user.is_staff else (),
        "querystring": query.urlencode(),
    }
    return render(request, "predictions/history.html", context)
