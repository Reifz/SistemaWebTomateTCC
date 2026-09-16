from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authentication import TokenAuthentication

from alerts.models import Alert
from captures.models import Capture
from dashboard.services import resumo_dashboard
from sensors.models import EnvironmentalReading

from .serializers import (
    AlertaSerializer,
    CapturaSerializer,
    EntradaCapturaSerializer,
    EntradaPredicaoSerializer,
    PredicaoSerializer,
)

@method_decorator(csrf_exempt, name='dispatch')
class CapturaView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        serializer = EntradaCapturaSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        dados = serializer.validated_data

        with transaction.atomic():
            captura = Capture.objects.create(
                user=request.user,
                image=dados["image"],
                observation=dados.get("observation", ""),
                origin=Capture.Origin.ESP32,
                status=Capture.Status.PENDING,
            )

            EnvironmentalReading.objects.create(
                capture=captura,
                temperature=dados["temperature"],
                humidity=dados["humidity"],
            )

        resposta = CapturaSerializer(captura)
        return Response(resposta.data, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name='dispatch')
class PredicaoView(APIView):
    def post(self, request):
        return Response(
            {"detail": "Inferência do modelo ainda não implementada."},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )


@method_decorator(csrf_exempt, name='dispatch')
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


@method_decorator(csrf_exempt, name='dispatch')
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