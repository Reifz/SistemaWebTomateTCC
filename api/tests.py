from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

class TestesApi(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            email="api@example.com",
            password="test-pass-123",
        )
        self.client = APIClient()

    def test_api_exige_autenticacao(self):
        resposta = self.client.get(reverse("api_dashboard_summary"))
        self.assertIn(resposta.status_code, (401, 403))

    def test_captura_aguarda_integracao_com_dispositivo(self):
        self.client.force_authenticate(self.usuario)
        resposta = self.client.post(reverse("api_capture"))
        self.assertEqual(resposta.status_code, 501)

    def test_predicao_aguarda_integracao_com_modelo(self):
        self.client.force_authenticate(self.usuario)
        resposta = self.client.post(
            reverse("api_prediction"),
            {"capture_id": 1},
            format="json"
        )
        self.assertEqual(resposta.status_code, 501)
