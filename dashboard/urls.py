from django.urls import path
from .views import imagem_resultado_manual, inicio, painel

urlpatterns = [
    path("", inicio, name="inicio"),
    path("dashboard/", painel, name="painel"),
    path("resultados/<str:id_execucao>/<str:tipo_imagem>/", imagem_resultado_manual, name="imagem_resultado_manual"),
]
