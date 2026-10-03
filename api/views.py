import tempfile
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, permissions, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from alerts.models import Alerta
from captures.models import Captura
from dashboard.services import resumo_painel
from predictions.models import Predicao
from predictions.services import (
    ImagemInvalida,
    LeituraInvalida,
    ModeloIndisponivel,
    ProcessamentoEmAndamento,
    processar_captura,
)
from sensors.models import LeituraAmbiental

from .serializers import (
    SerializadorAlerta,
    SerializadorCaptura,
    SerializadorEntradaCaptura,
    SerializadorEntradaPredicao,
    SerializadorPredicao,
)


@method_decorator(csrf_exempt, name='dispatch')
class VisaoCaptura(APIView):
    """
    Endpoint para registro de novas capturas (imagem e leituras de sensores ambientais).
    Recebe requisições do dispositivo IoT (ex: ESP32) ou aplicativo, insere os registros
    em transação atômica e retorna os dados encapsulados da captura.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        # Valida os dados de entrada usando o serializador dedicado
        serializador = SerializadorEntradaCaptura(data=request.data)

        if not serializador.is_valid():
            return Response(serializador.errors, status=status.HTTP_400_BAD_REQUEST)

        dados = serializador.validated_data

        # Garante atomicidade: tanto a captura quanto a leitura ambiental são persistidas juntas
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

        # Serializa e retorna a resposta formatada com status HTTP 201 (Created)
        resposta = SerializadorCaptura(captura)

        return Response(resposta.data, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name='dispatch')
class VisaoPredicao(APIView):
    """
    Endpoint para solicitar ou recuperar a inferência/predição de IA para uma captura existente.
    Trata exceções customizadas de negócio e as mapeia para códigos de status HTTP adequados.
    """

    def post(self, request):
        serializador = SerializadorEntradaPredicao(data=request.data)

        if not serializador.is_valid():
            return Response(serializador.errors, status=status.HTTP_400_BAD_REQUEST)

        # Garante que a captura pertença ao usuário autenticado (isolamento multitenant)
        captura = get_object_or_404(
            Captura.objects.filter(usuario=request.user),
            pk=serializador.validated_data["capture_id"],
        )

        # Invoca o pipeline de inferência e trata as possíveis exceções do serviço
        try:
            predicao, criada = processar_captura(captura)
        except ProcessamentoEmAndamento as erro:
            return Response({"detail": str(erro)}, status=status.HTTP_409_CONFLICT)
        except (ImagemInvalida, LeituraInvalida) as erro:
            return Response({"detail": str(erro)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except ModeloIndisponivel as erro:
            return Response({"detail": str(erro)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        resposta = SerializadorPredicao(predicao, context={"request": request})

        # Retorna HTTP 201 se o registro foi recém-criado ou HTTP 200 se já existia
        codigo = status.HTTP_201_CREATED if criada else status.HTTP_200_OK

        return Response(resposta.data, status=codigo)


class VisaoArtefatoPredicao(APIView):
    """
    Entrega arquivos de imagens derivadas do processamento (imagem processada ou imagem guia).
    Garante controle de acesso restrito ao proprietário da captura ou administradores (staff)
    e inclui proteção contra vulnerabilidades de Path Traversal.
    """

    def get(self, request, id_predicao, tipo_artefato):
        predicoes = Predicao.objects.select_related("captura")

        # Se não for staff, limita a busca às predições do próprio usuário
        if not request.user.is_staff:
            predicoes = predicoes.filter(captura__usuario=request.user)

        predicao = get_object_or_404(predicoes, pk=id_predicao)

        # Mapeia o parâmetro da rota para o caminho interno armazenado
        caminhos = {
            "processed": predicao.caminho_imagem_processada,
            "guide": predicao.caminho_imagem_guia,
        }

        caminho_relativo = caminhos.get(tipo_artefato)

        if not caminho_relativo:
            raise Http404

        raiz = Path(settings.RESULTS_ROOT).resolve()

        # Resolve o caminho final do arquivo no sistema de arquivos
        caminho = (raiz / caminho_relativo).resolve()

        # Proteção contra Path Traversal: valida se o arquivo está dentro do diretório raiz e se de fato existe
        if not caminho.is_relative_to(raiz) or not caminho.is_file():
            raise Http404

        # Retorna o arquivo de imagem para download/exibição direta
        return FileResponse(caminho.open("rb"), content_type="image/jpeg")


@method_decorator(csrf_exempt, name='dispatch')
class VisaoResumoPainel(APIView):
    """
    Endpoint agregador para dados do dashboard do usuário.
    Consome o serviço `resumo_painel` e traduz as chaves internas para a nomenclatura
    padrão da API em inglês (contrato público).
    """

    def get(self, request):
        resumo = resumo_painel(request.user)

        predicao_recente = resumo["ultima_predicao"]

        # Montagem do contrato do payload JSON traduzido para inglês
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
    """
    Endpoint genérico baseado em classe (ListAPIView) para listagem dos alertas do usuário.
    Suporta filtragem via query parameters por severidade e status de visualização.
    """
    serializer_class = SerializadorAlerta

    def get_queryset(self):
        # Filtra os alertas pertencentes unicamente ao usuário autenticado
        alertas = Alerta.objects.filter(captura__usuario=self.request.user)

        gravidade = self.request.query_params.get("severity")
        visualizado = self.request.query_params.get("viewed")

        # Aplica filtro por nível de severidade se fornecido na URL
        if gravidade:
            alertas = alertas.filter(severidade=gravidade)

        # Aplica filtro booleano por status de leitura se fornecido
        if visualizado in ("0", "1", "true", "false"):
            alertas = alertas.filter(visualizado=visualizado in ("1", "true"))

        return alertas