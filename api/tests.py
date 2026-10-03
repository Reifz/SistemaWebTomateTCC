import tempfile
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from captures.models import Captura
from predictions.models import Predicao


class TestesApi(TestCase):
    """
    Suíte de testes automatizados de integração para as rotas da API REST.
    Garante o contrato das respostas (chaves em inglês), o controle de acesso (permissões multitenant),
    o comportamento do envio de uploads/payloads e a execução do pipeline de predição.
    """

    def setUp(self):
        """
        Configura o ambiente inicial antes de cada método de teste:
        Cria um usuário padrão para autenticação e inicializa o cliente de testes da API REST Framework.
        """
        self.usuario = get_user_model().objects.create_user(
            email="api@example.com",
            password="test-pass-123",
        )

        self.client = APIClient()

    @staticmethod
    def _imagem_jpeg():
        """
        Método utilitário para gerar dinamicamente em memória um arquivo de imagem JPEG válido (16x16 pixels).
        Evita a dependência de arquivos físicos estáticos no disco para os testes de upload.
        """
        conteudo = BytesIO()

        # Cria uma imagem sólida no formato RGB e salva no buffer de memória
        Image.new("RGB", (16, 16), color=(40, 150, 60)).save(conteudo, format="JPEG")

        # Retorna a imagem encapsulada como um arquivo pronto para ser enviado via requisição HTTP
        return SimpleUploadedFile("folha.jpg", conteudo.getvalue(), content_type="image/jpeg")

    def test_api_exige_autenticacao(self):
        """
        Garante que requisições não autenticadas (sem token/sessão) sejam bloqueadas
        com os códigos HTTP de erro 401 (Unauthorized) ou 403 (Forbidden).
        """
        resposta = self.client.get(reverse("api_resumo_painel"))

        self.assertIn(resposta.status_code, (401, 403))

    def test_captura_rejeita_payload_incompleto(self):
        """
        Garante que o endpoint de criação de captura retorne erro HTTP 400 (Bad Request)
        quando a requisição é enviada sem os dados/campos obrigatórios.
        """
        self.client.force_authenticate(self.usuario)

        resposta = self.client.post(reverse("api_captura"))

        self.assertEqual(resposta.status_code, 400)

    @patch("api.views.processar_captura")
    def test_predicao_executa_pipeline_real(self, processar):
        """
        Testa a rota de execução da predição via API simulando a execução do pipeline do modelo (MobileSAM/Inferencia).
        Verifica se o endpoint responde com status 201 (Created) e se os dados processados retornam corretamente.
        """
        self.client.force_authenticate(self.usuario)

        # Prepara a estrutura prévia no banco de dados
        captura = Captura.objects.create(usuario=self.usuario)

        predicao = Predicao.objects.create(
            captura=captura,
            classe_prevista="Tomato___healthy",
            confianca=99,
            tres_principais=[
                {"class": "Tomato___healthy", "confidence": 99},
                {"class": "Tomato___Late_blight", "confidence": 0.6},
                {"class": "Tomato___Early_blight", "confidence": 0.4},
            ],
            nivel_confianca=Predicao.NivelConfianca.ALTA,
            id_execucao="20261001_120000_12345678",
            status_preprocessamento=Predicao.StatusPreprocessamento.SEGMENTADA,
            tempo_inferencia_ms=120,
            tempo_mobilesam_ms="450.125",
            dispositivo_processamento="cpu",
        )

        # Define que o mock da função de serviço 'processar_captura' retornará o objeto de predição e o flag Sucesso
        processar.return_value = predicao, True

        resposta = self.client.post(
            reverse("api_predicao"),
            {"capture_id": captura.pk},
            format="json",
        )

        # Validações dos resultados da API
        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(resposta.data["predicted_class"], "Tomato___healthy")
        self.assertEqual(resposta.data["inference_time_ms"], 120)

    def test_predicao_nao_acessa_captura_de_outro_usuario(self):
        """
        Testa a segurança de escopo multitenant: garante que um usuário autenticado
        não consiga solicitar a predição para uma captura pertencente a outro usuário (deve retornar HTTP 404).
        """
        outro_usuario = get_user_model().objects.create_user(
            email="other-api@example.com",
            password="test-pass-123",
        )

        captura = Captura.objects.create(usuario=outro_usuario)

        # Autentica com o usuário primário do teste
        self.client.force_authenticate(self.usuario)

        resposta = self.client.post(
            reverse("api_predicao"),
            {"capture_id": captura.pk},
            format="json",
        )

        self.assertEqual(resposta.status_code, 404)

    def test_resumo_preserva_chaves_publicas_em_ingles(self):
        """
        Valida o contrato de API da rota do resumo do painel: garante que o JSON de retorno
        contenha todas as chaves padrão da API expostas em inglês.
        """
        self.client.force_authenticate(self.usuario)

        resposta = self.client.get(reverse("api_resumo_painel"))

        self.assertEqual(resposta.status_code, 200)

        # Verifica se o conjunto de chaves obrigatórias do contrato público está presente na resposta
        self.assertTrue(
            {
                "total_captures",
                "processed_captures",
                "active_alerts",
                "latest_temperature",
                "latest_humidity",
                "latest_prediction",
                "diseases_detected",
                "low_confidence",
                "distribution",
                "readings",
                "class_statistics",
                "top_classes",
                "alerts_timeline",
                "alerts_timeline_has_data",
            }.issubset(resposta.data)
        )

    def test_captura_preserva_payload_publico_em_ingles(self):
        """
        Testa o envio multipart de imagem e leitura ambiental para a rota de captura.
        Utiliza diretório temporário para isolar e limpar os arquivos gerados durante o upload no teste.
        Valida se o payload retornado segue a nomenclatura em inglês definida no contrato da API.
        """
        self.client.force_authenticate(self.usuario)

        # Sobrescreve o MEDIA_ROOT do Django para salvar o upload em uma pasta temporária e isolada
        with tempfile.TemporaryDirectory() as pasta_midia, override_settings(MEDIA_ROOT=pasta_midia):
            resposta = self.client.post(
                reverse("api_captura"),
                {
                    "image": self._imagem_jpeg(),
                    "observation": "Contrato preservado",
                    "temperature": "25.00",
                    "humidity": "70.00",
                },
                format="multipart",
            )

        self.assertEqual(resposta.status_code, 201)

        # Valida as chaves estruturais presentes na resposta
        self.assertTrue(
            {
                "id",
                "origin",
                "status",
                "observation",
                "captured_at",
                "environmental_reading",
            }.issubset(resposta.data)
        )