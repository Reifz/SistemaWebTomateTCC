from django.urls import path
from . import views

urlpatterns = [
    path("profile/", views.perfil, name="perfil"),
    path("data/insert/", views.inserir_dados, name="inserir_dados"),
    path("data/truncate/", views.truncar_dados, name="truncar_dados"),
    path("", views.listar_usuarios, name="lista_usuarios"),
    path("new/", views.criar_usuario, name="criar_usuario"),
    path("<int:id_usuario>/edit/", views.editar_usuario, name="editar_usuario"),
]
