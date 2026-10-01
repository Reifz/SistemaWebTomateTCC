from django.urls import path
from .views import (
    VisaoCaptura,
    VisaoArtefatoPredicao,
    VisaoListaAlertas,
    VisaoPredicao,
    VisaoResumoPainel,
)

urlpatterns = [
    path("captures/", VisaoCaptura.as_view(), name="api_captura"),
    path("predictions/", VisaoPredicao.as_view(), name="api_predicao"),
    path(
        "predictions/<int:id_predicao>/artifacts/<str:tipo_artefato>/",
        VisaoArtefatoPredicao.as_view(),
        name="api_artefato_predicao",
    ),
    path("dashboard/summary/", VisaoResumoPainel.as_view(), name="api_resumo_painel"),
    path("alerts/", VisaoListaAlertas.as_view(), name="api_alertas"),
]
