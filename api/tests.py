import tempfile
from decimal import Decimal
from io import BytesIO
from pathlib import Path
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

        processar.assert_called_once_with(captura)

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

    @patch("api.views.processar_captura")
    def test_captura_preserva_payload_publico_em_ingles(self, processar):
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

        processar.assert_called_once()

    @patch("api.views.processar_captura")
    def test_captura_e_processada_automaticamente(self, processar):
        self.client.force_authenticate(self.usuario)

        def concluir_processamento(captura):
            Captura.objects.filter(pk=captura.pk).update(
                status=Captura.Status.PROCESSADA
            )

            return None, True

        processar.side_effect = concluir_processamento

        with tempfile.TemporaryDirectory() as pasta_midia, override_settings(MEDIA_ROOT=pasta_midia):
            resposta = self.client.post(
                reverse("api_captura"),
                {
                    "image": self._imagem_jpeg(),
                    "temperature": "25.00",
                    "humidity": "70.00",
                },
                format="multipart",
            )

        captura = Captura.objects.get()

        self.assertEqual(resposta.status_code, 201)

        self.assertEqual(resposta.data["status"], Captura.Status.PROCESSADA)

        processar.assert_called_once_with(captura)

    @patch("api.views.processar_captura")
    def test_captura_converte_leituras_nulas_em_zero(self, processar):
        self.client.force_authenticate(self.usuario)

        cenarios = (
            ("", "70.00", Decimal("0.00"), Decimal("70.00")),
            ("25.00", "", Decimal("25.00"), Decimal("0.00")),
            ("", "", Decimal("0.00"), Decimal("0.00")),
        )

        with tempfile.TemporaryDirectory() as pasta_midia, override_settings(MEDIA_ROOT=pasta_midia):
            for temperatura, umidade, temperatura_esperada, umidade_esperada in cenarios:
                with self.subTest(temperatura=temperatura, umidade=umidade):
                    resposta = self.client.post(
                        reverse("api_captura"),
                        {
                            "image": self._imagem_jpeg(),
                            "temperature": temperatura,
                            "humidity": umidade,
                        },
                        format="multipart",
                    )

                    self.assertEqual(resposta.status_code, 201)

                    leitura = Captura.objects.latest("pk").leitura_ambiental

                    self.assertEqual(leitura.temperatura, temperatura_esperada)

                    self.assertEqual(leitura.umidade, umidade_esperada)

    def test_captura_rejeita_leituras_ambientais_invalidas(self):
        self.client.force_authenticate(self.usuario)

        cenarios = (
            ({"temperature": "30.00"}, "humidity"),
            ({"temperature": "inválida", "humidity": "50.00"}, "temperature"),
            ({"temperature": "NaN", "humidity": "50.00"}, "temperature"),
            ({"temperature": "Infinity", "humidity": "50.00"}, "temperature"),
            ({"temperature": "-1.00", "humidity": "50.00"}, "temperature"),
            ({"temperature": "61.00", "humidity": "50.00"}, "temperature"),
            ({"temperature": "30.00", "humidity": "-1.00"}, "humidity"),
            ({"temperature": "30.00", "humidity": "101.00"}, "humidity"),
        )

        with tempfile.TemporaryDirectory() as pasta_midia, override_settings(MEDIA_ROOT=pasta_midia):
            for leitura, campo_com_erro in cenarios:
                with self.subTest(leitura=leitura):
                    resposta = self.client.post(
                        reverse("api_captura"),
                        {"image": self._imagem_jpeg(), **leitura},
                        format="multipart",
                    )

                    self.assertEqual(400, resposta.status_code)

                    self.assertIn(campo_com_erro, resposta.data)

    @patch("api.views.processar_captura")
    def test_captura_aceita_limites_ambientais_inclusivos(self, processar):
        self.client.force_authenticate(self.usuario)

        with tempfile.TemporaryDirectory() as pasta_midia, override_settings(MEDIA_ROOT=pasta_midia):
            for temperatura, umidade in (("0.00", "0.00"), ("60.00", "100.00")):
                with self.subTest(temperatura=temperatura, umidade=umidade):
                    resposta = self.client.post(
                        reverse("api_captura"),
                        {
                            "image": self._imagem_jpeg(),
                            "temperature": temperatura,
                            "humidity": umidade,
                        },
                        format="multipart",
                    )

                    self.assertEqual(201, resposta.status_code)

    def test_artefatos_preservam_tipos_png_e_jpeg(self):
        self.client.force_authenticate(self.usuario)

        with tempfile.TemporaryDirectory() as pasta_resultados, override_settings(
            RESULTS_ROOT=pasta_resultados
        ):
            for indice, (extensao, tipo_conteudo) in enumerate(
                (("png", "image/png"), ("jpg", "image/jpeg")),
                start=1,
            ):
                with self.subTest(extensao=extensao):
                    caminho_relativo = Path(
                        f"execucao_{indice}/preprocessamento/imagem_processada.{extensao}"
                    )

                    caminho_absoluto = Path(pasta_resultados) / caminho_relativo

                    caminho_absoluto.parent.mkdir(parents=True)

                    Image.new("RGB", (16, 16), color=(40, 150, 60)).save(
                        caminho_absoluto
                    )

                    captura = Captura.objects.create(usuario=self.usuario)

                    predicao = Predicao.objects.create(
                        captura=captura,
                        classe_prevista="Tomato___healthy",
                        confianca=99,
                        tres_principais=[{}, {}, {}],
                        nivel_confianca=Predicao.NivelConfianca.ALTA,
                        caminho_imagem_processada=caminho_relativo.as_posix(),
                    )

                    resposta = self.client.get(
                        reverse(
                            "api_artefato_predicao",
                            args=(predicao.pk, "processed"),
                        )
                    )

                    self.assertEqual(resposta.status_code, 200)

                    self.assertEqual(resposta["Content-Type"], tipo_conteudo)

                    resposta.close()
