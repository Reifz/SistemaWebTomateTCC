from django.contrib import admin
from .models import Alert


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("type", "severity", "capture", "viewed", "created_at")
    list_filter = ("type", "severity", "viewed", "created_at")
    search_fields = ("message", "capture__user__email")
