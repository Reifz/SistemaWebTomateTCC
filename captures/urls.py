from django.urls import path
from . import views

urlpatterns = [
    path("", views.listar_capturas, name="lista_capturas"),
    path("new/", views.criar_captura, name="criar_captura"),
    path("<int:id_captura>/", views.detalhar_captura, name="detalhar_captura"),
    path("<int:id_captura>/process/", views.processar_captura_existente, name="processar_captura"),
]
