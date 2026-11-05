from django.contrib import admin

from .models import Dispositivo


@admin.register(Dispositivo)
class DispositivoAdmin(admin.ModelAdmin):
    list_display = ("identificador", "nome", "usuario", "localizacao", "status", "atualizado_em")
    list_filter = ("status",)
    search_fields = ("identificador", "nome", "usuario__email", "localizacao")
