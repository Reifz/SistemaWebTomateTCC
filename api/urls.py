from django.urls import path
from .views import (
    CapturaView,
    ListaAlertasView,
    PredicaoView,
    ResumoDashboardView,
)

urlpatterns = [
    # Endpoint que o ESP32-CAM deverá chamar para enviar imagem e telemetria.
    path("captures/", CapturaView.as_view(), name="api_capture"),
    # Pode ser chamado pelo cliente após criar a captura ou substituído por uma
    # tarefa automática iniciada em CapturaView.
    path("predictions/", PredicaoView.as_view(), name="api_prediction"),
    # Os endpoints abaixo são de leitura para o dashboard/aplicações clientes.
    path("dashboard/summary/", ResumoDashboardView.as_view(), name="api_dashboard_summary"),
    path("alerts/", ListaAlertasView.as_view(), name="api_alerts"),
]
