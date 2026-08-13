from django.urls import path
from .views import imagem_resultado_manual, inicio, painel

urlpatterns = [
    path("", inicio, name="home"),
    path("dashboard/", painel, name="dashboard"),
    path("resultados/<str:run_id>/<str:image_type>/", imagem_resultado_manual, name="manual_result_image"),
]
