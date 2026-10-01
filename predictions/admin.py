from django.contrib import admin
from .models import Predicao


@admin.register(Predicao)
class AdministracaoPredicao(admin.ModelAdmin):
    list_display = (
        "captura",
        "classe_prevista",
        "confianca",
        "nivel_confianca",
        "status_preprocessamento",
        "tempo_inferencia_ms",
        "prevista_em",
    )

    list_filter = (
        "nivel_confianca",
        "status_preprocessamento",
        "classe_prevista",
        "prevista_em",
    )

    search_fields = ("classe_prevista", "captura__usuario__email")
