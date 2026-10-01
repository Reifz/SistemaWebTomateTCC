from django.contrib import admin
from .models import Captura


@admin.register(Captura)
class AdministracaoCaptura(admin.ModelAdmin):
    list_display = ("id", "usuario", "origem", "status", "capturada_em")

    list_filter = ("origem", "status", "capturada_em")

    search_fields = ("usuario__email", "observacao")
