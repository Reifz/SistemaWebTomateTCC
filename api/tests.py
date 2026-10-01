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
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            email="api@example.com",
            password="test-pass-123",
        )

        self.client = APIClient()

    @staticmethod
    def _imagem_jpeg():
        conteudo = BytesIO()

        Image.new("RGB", (16, 16), color=(40, 150, 60)).save(conteudo, format="JPEG")

        return SimpleUploadedFile("folha.jpg", conteudo.getvalue(), content_type="image/jpeg")

    def test_api_exige_autenticacao(self):
        resposta = self.client.get(reverse("api_resumo_painel"))

        self.assertIn(resposta.status_code, (401, 403))

    def test_captura_rejeita_payload_incompleto(self):
        self.client.force_authenticate(self.usuario)

        resposta = self.client.post(reverse("api_captura"))

        self.assertEqual(resposta.status_code, 400)

    @patch("api.views.processar_captura")
    def test_predicao_executa_pipeline_real(self, processar):
        self.client.force_authenticate(self.usuario)

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

        processar.return_value = predicao, True

        resposta = self.client.post(
            reverse("api_predicao"),
            {"capture_id": captura.pk},
            format="json",
        )

        self.assertEqual(resposta.status_code, 201)

        self.assertEqual(resposta.data["predicted_class"], "Tomato___healthy")

        self.assertEqual(resposta.data["inference_time_ms"], 120)

    def test_predicao_nao_acessa_captura_de_outro_usuario(self):
        outro_usuario = get_user_model().objects.create_user(
            email="other-api@example.com",
            password="test-pass-123",
        )

        captura = Captura.objects.create(usuario=outro_usuario)

        self.client.force_authenticate(self.usuario)

        resposta = self.client.post(
            reverse("api_predicao"),
            {"capture_id": captura.pk},
            format="json",
        )

        self.assertEqual(resposta.status_code, 404)

    def test_resumo_preserva_chaves_publicas_em_ingles(self):
        self.client.force_authenticate(self.usuario)

        resposta = self.client.get(reverse("api_resumo_painel"))

        self.assertEqual(resposta.status_code, 200)

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
        self.client.force_authenticate(self.usuario)

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
