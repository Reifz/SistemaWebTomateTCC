from django.urls import path
from . import views

urlpatterns = [
    path("profile/", views.perfil, name="perfil"),
    path("data/insert/", views.inserir_dados, name="inserir_dados"),
    path("data/truncate/", views.truncar_dados, name="truncar_dados"),
    path("", views.user_list, name="user_list"),
    path("new/", views.user_create, name="user_create"),
    path("<int:pk>/edit/", views.user_edit, name="user_edit"),
]
