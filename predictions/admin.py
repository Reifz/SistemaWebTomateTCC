from django.contrib import admin
from .models import Prediction


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ("capture", "predicted_class", "confidence", "confidence_status", "predicted_at")
    list_filter = ("confidence_status", "predicted_class", "predicted_at")
    search_fields = ("predicted_class", "capture__user__email")
