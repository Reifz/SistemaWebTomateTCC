from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase

from alerts.models import Alert
from captures.models import Capture
from predictions.services import gerar_leitura_ambiental, nivel_confianca, processar_captura


class FixedRandom:
    """
    Dublê de teste (Mock/Stub) para substituir a aleatoriedade do módulo `random`.
    Garante comportamento determinístico durante os testes unitários.
    """
    def choice(self, values):
        # Retorna sempre o primeiro item da lista recebida
        return values[0]

    def sample(self, values, count):
        # Retorna os N primeiros elementos em ordem fixa
        return list(values[:count])


class PredictionServiceTests(TestCase):
    """
    Suíte de testes automatizados unitários e de integração para os serviços
    de processamento de capturas, medição ambiental e regras de alerta.
    """

    def setUp(self):
        """Prepara os dados iniciais reutilizados pelos cenários de teste."""
        self.user = get_user_model().objects.create_user(
            email="test@example.com", 
            password="test-pass-123"
        )

    def capture_with_humidity(self, humidity):
        """Função auxiliar para criar uma captura associada a uma leitura ambiental de umidade específica."""
        capture = Capture.objects.create(user=self.user, origin=Capture.Origin.SIMULATED)
        gerar_leitura_ambiental(capture, 25, humidity)
        return capture

    def test_confidence_boundaries(self):
        """Valida se os limites exatos (valores de borda) de confiança alteram o status corretamente."""
        self.assertEqual(nivel_confianca(Decimal("59.99")), "baixa")
        self.assertEqual(nivel_confianca(Decimal("60")), "media")
        self.assertEqual(nivel_confianca(Decimal("79.99")), "media")
        self.assertEqual(nivel_confianca(Decimal("80")), "alta")

    def test_low_confidence_creates_retake_alert(self):
        """Garante que predições com confiança baixa (< 60%) geram apenas o alerta de refazer captura."""
        prediction, created = processar_captura(
            self.capture_with_humidity(60), 
            gerador=FixedRandom(), 
            classe_prevista="Tomato___Early_blight", 
            confianca=59
        )
        self.assertTrue(created)
        self.assertEqual(
            list(prediction.alerts.values_list("type", flat=True)), 
            [Alert.Type.LOW_CONFIDENCE]
        )

    def test_disease_high_confidence_and_humidity_create_three_alerts(self):
        """
        Garante que uma predição com doença identificada com alta confiança e
        umidade elevada gera os 3 alertas combinados: Fitossanitário, Crítico e Ambiental.
        """
        prediction, _ = processar_captura(
            self.capture_with_humidity(85), 
            gerador=FixedRandom(), 
            classe_prevista="Tomato___Late_blight", 
            confianca=80
        )
        self.assertSetEqual(
            set(prediction.alerts.values_list("type", flat=True)), 
            {Alert.Type.PHYTOSANITARY, Alert.Type.CRITICAL, Alert.Type.ENVIRONMENTAL}
        )

    def test_healthy_high_confidence_only_creates_environmental_alert(self):
        """
        Garante que plantas saudáveis, mesmo sob condições de alta umidade,
        não gerem alertas de doença, apenas o alerta ambiental relativo ao clima.
        """
        prediction, _ = processar_captura(
            self.capture_with_humidity(90), 
            gerador=FixedRandom(), 
            classe_prevista="Tomato___healthy", 
            confianca=90
        )
        self.assertEqual(
            list(prediction.alerts.values_list("type", flat=True)), 
            [Alert.Type.ENVIRONMENTAL]
        )

    def test_processing_is_idempotent(self):
        """
        Valida a idempotência da função `processar_captura`: reprocessar a mesma captura
        deve retornar a predição existente sem criar novos registros ou duplicar alertas.
        """
        capture = self.capture_with_humidity(60)
        
        # Primeiro processamento: deve criar a predição
        first, first_created = processar_captura(capture, gerador=FixedRandom(), confianca=70)
        
        # Segundo processamento na mesma captura: deve reaproveitar a predição existente
        second, second_created = processar_captura(capture, gerador=FixedRandom(), confianca=90)
        
        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(capture.alerts.count(), 0)