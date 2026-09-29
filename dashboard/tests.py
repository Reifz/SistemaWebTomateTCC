from datetime import timedelta

from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from alerts.models import Alert
from captures.models import Capture
from predictions.models import Prediction
from sensors.models import EnvironmentalReading

from .services import resumo_dashboard


class DashboardTests(TestCase):
    def criar_predicao(self, usuario, classe, confianca, umidade, severidade=None):
        captura = Capture.objects.create(user=usuario, status=Capture.Status.PROCESSED)
        EnvironmentalReading.objects.create(capture=captura, temperature=25, humidity=umidade)
        predicao = Prediction.objects.create(
            capture=captura,
            predicted_class=classe,
            confidence=confianca,
            confidence_status=Prediction.ConfidenceStatus.HIGH,
            top_three=[{}, {}, {}],
        )
        if severidade:
            Alert.objects.create(
                capture=captura,
                prediction=predicao,
                type=Alert.Type.ENVIRONMENTAL,
                severity=severidade,
                message="Alerta de teste",
            )
        return captura, predicao

    def test_templates_nao_possuem_quebras_de_linha_literais(self):
        for arquivo in (settings.BASE_DIR / "templates").rglob("*.html"):
            with self.subTest(arquivo=arquivo.name):
                bytes_do_arquivo = arquivo.read_bytes()
                self.assertFalse(bytes_do_arquivo.startswith(b"\xef\xbb\xbf"))
                conteudo = bytes_do_arquivo.decode("utf-8")
                self.assertNotIn("`r`n", conteudo)
                self.assertFalse(conteudo.endswith("\n\n"))

    def test_home_renders_after_login(self):
        user = get_user_model().objects.create_user(email="home@example.com", password="test-pass-123")
        self.client.force_login(user)
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="card-header"', count=4)
        self.assertContains(response, 'class="card-header section-heading"', count=2)
        self.assertContains(response, "Monitoramento inteligente")
        self.assertContains(response, "font-awesome/6.7.2/css/all.min.css")
        self.assertContains(response, 'class="fa-solid fa-house nav-link-icon"')

    def test_navbar_administrativo_exibe_icones_font_awesome(self):
        usuario = get_user_model().objects.create_user(
            email="icones@example.com",
            password="test-pass-123",
            is_staff=True,
        )
        self.client.force_login(usuario)

        resposta = self.client.get(reverse("home"))

        for classe in ("fa-house", "fa-chart-line", "fa-camera", "fa-clock-rotate-left", "fa-bell", "fa-users"):
            with self.subTest(classe=classe):
                self.assertContains(resposta, classe)

    def test_telas_internas_usam_paineis_de_cabecalho_e_conteudo(self):
        usuario = get_user_model().objects.create_user(
            email="paineis@example.com",
            password="test-pass-123",
            is_staff=True,
        )
        self.client.force_login(usuario)

        for rota in ("home", "dashboard", "capture_list", "capture_create", "history", "alert_list", "user_list"):
            with self.subTest(rota=rota):
                resposta = self.client.get(reverse(rota))
                self.assertContains(resposta, "painel-cabecalho")
                self.assertContains(resposta, "painel-conteudo")

    def test_listagens_usam_card_interno_para_tabela(self):
        usuario = get_user_model().objects.create_user(
            email="tabelas@example.com",
            password="test-pass-123",
            is_staff=True,
        )
        self.client.force_login(usuario)

        for rota in ("capture_list", "history", "alert_list", "user_list"):
            with self.subTest(rota=rota):
                resposta = self.client.get(reverse(rota))
                self.assertContains(resposta, 'class="content-card content-card-com-header"')
                self.assertContains(resposta, 'class="card-header"')
                self.assertContains(resposta, 'class="card-body p-0 table-responsive"')

    def test_dashboard_renders_for_authenticated_user(self):
        user = get_user_model().objects.create_user(email="dash@example.com", password="test-pass-123")
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")
        self.assertContains(response, 'class="btn btn-success btn-sm"')

    def test_cards_com_cabecalho_nao_reintroduzem_padding_externo(self):
        css_principal = (settings.BASE_DIR / "static/css/app.css").read_text(encoding="utf-8")
        css_responsivo = (settings.BASE_DIR / "static/css/responsivo.css").read_text(encoding="utf-8")

        self.assertIn(".content-card.content-card-com-header {", css_principal)
        self.assertIn(".content-card.content-card-com-header {", css_responsivo)
        self.assertIn(".content-card-com-header .chart-empty", css_principal)

    def test_operational_pages_render_for_administrator(self):
        user = get_user_model().objects.create_user(email="staff@example.com", password="test-pass-123", is_staff=True)
        self.client.force_login(user)
        for route in ("home", "dashboard", "capture_list", "capture_create", "history", "alert_list", "user_list"):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse(route)).status_code, 200)

    def test_dashboard_vazio_exibe_mensagens_no_lugar_dos_graficos(self):
        usuario = get_user_model().objects.create_user(email="vazio@example.com", password="test-pass-123")
        self.client.force_login(usuario)
        resposta = self.client.get(reverse("dashboard"))
        self.assertContains(resposta, "Ainda não há análises para exibir")
        self.assertContains(resposta, "Ainda não há leituras ambientais")

    def test_dashboard_administrativo_usa_filtro_em_largura_completa(self):
        usuario = get_user_model().objects.create_user(
            email="filtro-dashboard@example.com",
            password="test-pass-123",
            is_staff=True,
        )
        self.client.force_login(usuario)

        resposta = self.client.get(reverse("dashboard"))

        self.assertContains(resposta, 'class="filter-fields"')
        self.assertContains(resposta, 'class="filter-actions"')
        self.assertContains(resposta, 'class="btn btn-dark btn-lg"')
        self.assertContains(resposta, ">Filtrar</button>")

    def test_estatisticas_de_classe_calculam_media_e_top_cinco(self):
        usuario = get_user_model().objects.create_user(email="classes@example.com", password="test-pass-123")
        self.criar_predicao(usuario, "Tomato___healthy", 80, 50)
        self.criar_predicao(usuario, "Tomato___healthy", 90, 55)
        self.criar_predicao(usuario, "Tomato___Late_blight", 70, 75)

        contexto = resumo_dashboard(usuario)

        saudavel = next(item for item in contexto["class_statistics"] if item["predicted_class"] == "Tomato___healthy")
        self.assertEqual(saudavel["total"], 2)
        self.assertEqual(saudavel["confianca_media"], 85.0)
        self.assertEqual(contexto["top_classes"][0]["predicted_class"], "Tomato___healthy")

    def test_alertas_temporais_tem_trinta_dias_e_zeros(self):
        usuario = get_user_model().objects.create_user(email="alertas-tempo@example.com", password="test-pass-123")
        _, predicao = self.criar_predicao(usuario, "Tomato___Late_blight", 90, 85, Alert.Severity.CRITICAL)
        alerta = predicao.alerts.get()
        Alert.objects.filter(pk=alerta.pk).update(created_at=timezone.now() - timedelta(days=2))

        contexto = resumo_dashboard(usuario)

        self.assertEqual(len(contexto["alerts_timeline"]), 30)
        self.assertEqual(sum(item["critica"] for item in contexto["alerts_timeline"]), 1)
        self.assertTrue(any(item["critica"] == 0 for item in contexto["alerts_timeline"]))

    def test_novos_dados_respeitam_isolamento_do_usuario(self):
        usuario = get_user_model().objects.create_user(email="isolado@example.com", password="test-pass-123")
        outro = get_user_model().objects.create_user(email="outro-dashboard@example.com", password="test-pass-123")
        self.criar_predicao(usuario, "Tomato___healthy", 88, 50)
        self.criar_predicao(outro, "Tomato___Late_blight", 99, 90, Alert.Severity.CRITICAL)

        contexto = resumo_dashboard(usuario)

        self.assertEqual(len(contexto["class_statistics"]), 1)
        self.assertEqual(contexto["class_statistics"][0]["predicted_class"], "Tomato___healthy")
        self.assertFalse(contexto["alerts_timeline_has_data"])

    def test_dashboard_renderiza_novos_componentes_e_estados_vazios(self):
        usuario = get_user_model().objects.create_user(email="graficos-vazios@example.com", password="test-pass-123")
        self.client.force_login(usuario)

        resposta = self.client.get(reverse("dashboard"))

        self.assertContains(resposta, "Confiança média por classe")
        self.assertContains(resposta, "Alertas por severidade")
        self.assertNotContains(resposta, "Umidade × doenças e alertas")
        self.assertContains(resposta, "5 classes mais detectadas")
        self.assertContains(resposta, "js/dashboard-graficos.js")
