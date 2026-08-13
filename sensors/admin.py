from django.contrib import admin
from .models import EnvironmentalReading


@admin.register(EnvironmentalReading)
class EnvironmentalReadingAdmin(admin.ModelAdmin):
    list_display = ("capture", "temperature", "humidity", "measured_at")
    list_filter = ("measured_at",)
