from django.urls import path
from . import views

urlpatterns = [
    path("", views.listar_alertas, name="lista_alertas"),
    path("<int:id_alerta>/read/", views.marcar_como_visualizado, name="visualizar_alerta"),
]
