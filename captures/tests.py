from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import Capture


class CaptureViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="web@example.com", password="test-pass-123")
        self.other = get_user_model().objects.create_user(email="other@example.com", password="test-pass-123")

    def test_views_redirect_anonymous_user(self):
        response = self.client.get(reverse("capture_list"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('capture_list')}")

    def test_create_capture_generates_environmental_reading(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("capture_create"), {"origin": "simulado", "observation": "Teste", "temperature": "24.50", "humidity": "70.00"})
        capture = Capture.objects.get(user=self.user)
        self.assertRedirects(response, reverse("capture_detail", args=[capture.pk]))
        self.assertEqual(capture.environmental_reading.humidity, 70)

    def test_capture_detail_is_isolated_by_user(self):
        capture = Capture.objects.create(user=self.other)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("capture_detail", args=[capture.pk])).status_code, 404)

    def test_detalhe_usa_paineis_de_cabecalho_e_conteudo(self):
        captura = Capture.objects.create(user=self.user)
        self.client.force_login(self.user)

        resposta = self.client.get(reverse("capture_detail", args=[captura.pk]))

        self.assertContains(resposta, "painel-cabecalho")
        self.assertContains(resposta, "painel-conteudo")
        self.assertContains(resposta, 'class="btn btn-light"')
        self.assertContains(resposta, 'class="content-card mb-3"', count=2)
        self.assertContains(resposta, '<div class="content-card">', count=1)

    def test_filtros_usam_layout_flexivel_e_botao_em_largura_completa(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        Capture.objects.create(user=self.user)
        self.client.force_login(self.user)
        resposta = self.client.get(reverse("capture_list"))
        self.assertContains(resposta, 'class="filter-fields"')
        self.assertContains(resposta, 'class="filter-field filter-field-search"')
        self.assertContains(resposta, 'class="filter-actions"')
        self.assertContains(resposta, 'class="btn btn-dark btn-lg"')
        self.assertNotContains(resposta, ">Limpar</a>")
        self.assertContains(resposta, 'class="btn btn-success btn-sm"')
