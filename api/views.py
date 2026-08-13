from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from alerts.models import Alert
from dashboard.services import resumo_dashboard
from .serializers import (
    AlertaSerializer,
    PredicaoSerializer,
)


class CapturaView(APIView):
    def post(self, request):
        # TODO: implementar a recepção dos dados enviados pelo ESP32-CAM.
        # Etapas esperadas:
        # 1. autenticar o dispositivo e obter seu usuário pelo token;
        # 2. validar imagem, temperatura e umidade com EntradaCapturaSerializer;
        # 3. criar Capture com origem Capture.Origin.ESP32;
        # 4. criar EnvironmentalReading ligada à captura;
        # 5. iniciar a inferência em uma tarefa assíncrona;
        # 6. responder com CapturaSerializer e HTTP 201.
        return Response(
            {"detail": "Integração com o ESP32-CAM ainda não implementada."},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )


class PredicaoView(APIView):
    def post(self, request):
        # TODO: implementar somente se a inferência precisar ser iniciada por uma
        # requisição separada. Se ela começar automaticamente em CapturaView,
        # remova esta view, sua rota e EntradaPredicaoSerializer.
        return Response(
            {"detail": "Inferência do modelo ainda não implementada."},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )


class ResumoDashboardView(APIView):
    def get(self, request):
        resumo = resumo_dashboard(request.user)
        predicao_recente = resumo.pop("latest_prediction")

        resumo["latest_prediction"] = (
            PredicaoSerializer(predicao_recente).data
            if predicao_recente
            else None
        )
        resumo["readings"] = [
            {
                "measured_at": leitura.measured_at,
                "temperature": leitura.temperature,
                "humidity": leitura.humidity,
            }
            for leitura in resumo["readings"]
        ]

        return Response(resumo)


class ListaAlertasView(generics.ListAPIView):
    serializer_class = AlertaSerializer

    def get_queryset(self):
        alertas = Alert.objects.filter(capture__user=self.request.user)
        gravidade = self.request.query_params.get("severity")
        visualizado = self.request.query_params.get("viewed")

        if gravidade:
            alertas = alertas.filter(severity=gravidade)
        if visualizado in ("0", "1", "true", "false"):
            alertas = alertas.filter(viewed=visualizado in ("1", "true"))

        return alertas
