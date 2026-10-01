from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authentication import TokenAuthentication

from alerts.models import Alerta
from captures.models import Captura
from dashboard.services import resumo_painel
from sensors.models import LeituraAmbiental
from predictions.models import Predicao
from predictions.services import (
    ImagemInvalida,
    LeituraInvalida,
    ModeloIndisponivel,
    ProcessamentoEmAndamento,
    processar_captura,
)

from .serializers import (
    SerializadorAlerta,
    SerializadorCaptura,
    SerializadorEntradaCaptura,
    SerializadorEntradaPredicao,
    SerializadorPredicao,
)


@method_decorator(csrf_exempt, name='dispatch')
class VisaoCaptura(APIView):
    authentication_classes = [TokenAuthentication]

    permission_classes = [permissions.IsAuthenticated]

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        serializador = SerializadorEntradaCaptura(data=request.data)

        if not serializador.is_valid():
            return Response(serializador.errors, status=status.HTTP_400_BAD_REQUEST)

        dados = serializador.validated_data

        with transaction.atomic():
            captura = Captura.objects.create(
                usuario=request.user,
                imagem=dados["image"],
                observacao=dados.get("observation", ""),
                origem=Captura.Origem.ESP32,
                status=Captura.Status.PENDENTE,
            )

            LeituraAmbiental.objects.create(
                captura=captura,
                temperatura=dados["temperature"],
                umidade=dados["humidity"],
            )

        resposta = SerializadorCaptura(captura)

        return Response(resposta.data, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name='dispatch')
class VisaoPredicao(APIView):
    def post(self, request):
        serializador = SerializadorEntradaPredicao(data=request.data)

        if not serializador.is_valid():
            return Response(serializador.errors, status=status.HTTP_400_BAD_REQUEST)

        captura = get_object_or_404(
            Captura.objects.filter(usuario=request.user),
            pk=serializador.validated_data["capture_id"],
        )

        try:
            predicao, criada = processar_captura(captura)
        except ProcessamentoEmAndamento as erro:
            return Response({"detail": str(erro)}, status=status.HTTP_409_CONFLICT)
        except (ImagemInvalida, LeituraInvalida) as erro:
            return Response({"detail": str(erro)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except ModeloIndisponivel as erro:
            return Response({"detail": str(erro)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        resposta = SerializadorPredicao(predicao, context={"request": request})

        codigo = status.HTTP_201_CREATED if criada else status.HTTP_200_OK

        return Response(resposta.data, status=codigo)


class VisaoArtefatoPredicao(APIView):
    """Entrega imagens derivadas somente ao proprietário ou administrador."""

    def get(self, request, id_predicao, tipo_artefato):
        predicoes = Predicao.objects.select_related("captura")

        if not request.user.is_staff:
            predicoes = predicoes.filter(captura__usuario=request.user)

        predicao = get_object_or_404(predicoes, pk=id_predicao)

        caminhos = {
            "processed": predicao.caminho_imagem_processada,
            "guide": predicao.caminho_imagem_guia,
        }

        caminho_relativo = caminhos.get(tipo_artefato)

        if not caminho_relativo:
            raise Http404

        raiz = Path(settings.RESULTS_ROOT).resolve()

        caminho = (raiz / caminho_relativo).resolve()

        if not caminho.is_relative_to(raiz) or not caminho.is_file():
            raise Http404

        return FileResponse(caminho.open("rb"), content_type="image/jpeg")


@method_decorator(csrf_exempt, name='dispatch')
class VisaoResumoPainel(APIView):
    def get(self, request):
        resumo = resumo_painel(request.user)

        predicao_recente = resumo["ultima_predicao"]

        resposta = {
            "total_captures": resumo["total_capturas"],
            "processed_captures": resumo["capturas_processadas"],
            "active_alerts": resumo["alertas_ativos"],
            "latest_temperature": resumo["ultima_temperatura"],
            "latest_humidity": resumo["ultima_umidade"],
            "latest_prediction": SerializadorPredicao(predicao_recente).data if predicao_recente else None,
            "diseases_detected": resumo["doencas_detectadas"],
            "low_confidence": resumo["baixa_confianca"],
            "distribution": [
                {"predicted_class": item["classe_prevista"], "total": item["total"]}
                for item in resumo["distribuicao"]
            ],
            "readings": [
                {
                    "measured_at": leitura["medida_em"],
                    "temperature": leitura["temperatura"],
                    "humidity": leitura["umidade"],
                }
                for leitura in resumo["leituras"]
            ],
            "class_statistics": [
                {
                    "predicted_class": item["classe_prevista"],
                    "total": item["total"],
                    "confianca_media": item["confianca_media"],
                }
                for item in resumo["estatisticas_classes"]
            ],
            "top_classes": [
                {
                    "predicted_class": item["classe_prevista"],
                    "total": item["total"],
                    "confianca_media": item["confianca_media"],
                }
                for item in resumo["principais_classes"]
            ],
            "alerts_timeline": [
                {"date": item["data"], **{chave: valor for chave, valor in item.items() if chave != "data"}}
                for item in resumo["linha_tempo_alertas"]
            ],
            "alerts_timeline_has_data": resumo["linha_tempo_alertas_possui_dados"],
        }

        return Response(resposta)


@method_decorator(csrf_exempt, name='dispatch')
class VisaoListaAlertas(generics.ListAPIView):
    serializer_class = SerializadorAlerta

    def get_queryset(self):
        alertas = Alerta.objects.filter(captura__usuario=self.request.user)

        gravidade = self.request.query_params.get("severity")

        visualizado = self.request.query_params.get("viewed")

        if gravidade:
            alertas = alertas.filter(severidade=gravidade)

        if visualizado in ("0", "1", "true", "false"):
            alertas = alertas.filter(visualizado=visualizado in ("1", "true"))

        return alertas
