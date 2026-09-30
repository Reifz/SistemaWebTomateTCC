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
    """
    Endpoint para registro de novas capturas de imagem e leituras ambientais.
    Requer autenticação via Token.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        # Validação dos dados recebidos na requisição
        serializer = EntradaCapturaSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        dados = serializer.validated_data

        # Garantia de integridade: a criação da captura e da leitura ambiental 
        # ocorre dentro de uma única transação no banco de dados.
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

        # Retorno do registro de captura recém-criado
        resposta = CapturaSerializer(captura)
        return Response(resposta.data, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name='dispatch')
class PredicaoView(APIView):
    """
    Endpoint reservado para o processamento de inferência do modelo de IA.
    Atualmente não implementado.
    """
    def post(self, request):
        return Response(
            {"detail": "Inferência do modelo ainda não implementada."},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )


@method_decorator(csrf_exempt, name='dispatch')
class ResumoDashboardView(APIView):
    """
    Endpoint para obtenção de dados consolidados do painel do usuário,
    incluindo última predição e leituras dos sensores.
    """
    def get(self, request):
        # Busca a estrutura básica do resumo para o usuário logado
        resumo = resumo_dashboard(request.user)
        predicao_recente = resumo.pop("latest_prediction")

        # Serialização da predição mais recente (caso exista)
        resumo["latest_prediction"] = (
            PredicaoSerializer(predicao_recente).data
            if predicao_recente
            else None
        )
        
        # Mapeamento e formatação das leituras ambientais
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
    """
    Endpoint para listagem filtrada dos alertas associados às capturas do usuário.
    """
    serializer_class = AlertaSerializer

    def get_queryset(self):
        # Filtra os alertas vinculados ao usuário autenticado
        alertas = Alert.objects.filter(capture__user=self.request.user)
        
        # Leitura dos parâmetros de URL para filtragem opcional
        gravidade = self.request.query_params.get("severity")
        visualizado = self.request.query_params.get("viewed")

        # Aplicação dos filtros condicionais
        if gravidade:
            alertas = alertas.filter(severity=gravidade)
        if visualizado in ("0", "1", "true", "false"):
            alertas = alertas.filter(viewed=visualizado in ("1", "true"))

        return alertas