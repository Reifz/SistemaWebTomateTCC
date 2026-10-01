from django.contrib import admin
from .models import LeituraAmbiental


@admin.register(LeituraAmbiental)
class AdministracaoLeituraAmbiental(admin.ModelAdmin):
    list_display = ("captura", "temperatura", "umidade", "medida_em")

    list_filter = ("medida_em",)
