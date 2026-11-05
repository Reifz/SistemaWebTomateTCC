from django.urls import path

from . import views


urlpatterns = [
    path("", views.listar_dispositivos, name="lista_dispositivos"),
    path("new/", views.criar_dispositivo, name="criar_dispositivo"),
    path("<int:id_dispositivo>/edit/", views.editar_dispositivo, name="editar_dispositivo"),
]
