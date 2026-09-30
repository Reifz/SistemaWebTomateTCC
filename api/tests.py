from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient


class TestesApi(TestCase):
    """
    Classe de testes de integração da API REST.
    Valida o controle de acesso, a autenticação e as rotas pendentes de implementação.
    """

    def setUp(self):
        """
        Método de preparação executado antes de cada teste.
        Cria um usuário de teste no banco e instancia o cliente de teste da API (APIClient).
        """
        self.usuario = get_user_model().objects.create_user(
            email="api@example.com",
            password="test-pass-123",
        )
        self.client = APIClient()

    def test_api_exige_autenticacao(self):
        """
        Verifica se o endpoint do resumo do dashboard bloqueia requisições não autenticadas,
        esperando um código de status 401 Unauthorized ou 403 Forbidden.
        """
        resposta = self.client.get(reverse("api_dashboard_summary"))
        self.assertIn(resposta.status_code, (401, 403))

    def test_captura_aguarda_integracao_com_dispositivo(self):
        """
        Garante que o endpoint de captura retorne 501 Not Implemented
        quando acionado por um usuário autenticado (aguardando integração com hardware/ESP32).
        """
        self.client.force_authenticate(self.usuario)
        resposta = self.client.post(reverse("api_capture"))
        self.assertEqual(resposta.status_code, 501)

    def test_predicao_aguarda_integracao_com_modelo(self):
        """
        Garante que o endpoint de predição retorne 501 Not Implemented
        ao receber os dados de payload (aguardando integração com o modelo de IA).
        """
        self.client.force_authenticate(self.usuario)
        resposta = self.client.post(
            reverse("api_prediction"),
            {"capture_id": 1},
            format="json"
        )
        self.assertEqual(resposta.status_code, 501)