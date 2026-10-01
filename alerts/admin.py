from django.contrib import admin
from .models import Alerta


@admin.register(Alerta)
class AdministracaoAlerta(admin.ModelAdmin):
    list_display = ("tipo", "severidade", "captura", "visualizado", "criado_em")

    list_filter = ("tipo", "severidade", "visualizado", "criado_em")

    search_fields = ("mensagem", "captura__usuario__email")
