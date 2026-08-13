from django.contrib import admin
from .models import Capture


@admin.register(Capture)
class CaptureAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "origin", "status", "captured_at")
    list_filter = ("origin", "status", "captured_at")
    search_fields = ("user__email", "observation")
