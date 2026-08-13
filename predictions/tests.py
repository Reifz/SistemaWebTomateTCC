from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase

from alerts.models import Alert
from captures.models import Capture
from predictions.services import gerar_leitura_ambiental, nivel_confianca, processar_captura


class FixedRandom:
    def choice(self, values):
        return values[0]

    def sample(self, values, count):
        return list(values[:count])


class PredictionServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="test@example.com", password="test-pass-123")

    def capture_with_humidity(self, humidity):
        capture = Capture.objects.create(user=self.user, origin=Capture.Origin.SIMULATED)
        gerar_leitura_ambiental(capture, 25, humidity)
        return capture

    def test_confidence_boundaries(self):
        self.assertEqual(nivel_confianca(Decimal("59.99")), "baixa")
        self.assertEqual(nivel_confianca(Decimal("60")), "media")
        self.assertEqual(nivel_confianca(Decimal("79.99")), "media")
        self.assertEqual(nivel_confianca(Decimal("80")), "alta")

    def test_low_confidence_creates_retake_alert(self):
        prediction, created = processar_captura(self.capture_with_humidity(60), gerador=FixedRandom(), classe_prevista="Tomato___Early_blight", confianca=59)
        self.assertTrue(created)
        self.assertEqual(list(prediction.alerts.values_list("type", flat=True)), [Alert.Type.LOW_CONFIDENCE])

    def test_disease_high_confidence_and_humidity_create_three_alerts(self):
        prediction, _ = processar_captura(self.capture_with_humidity(85), gerador=FixedRandom(), classe_prevista="Tomato___Late_blight", confianca=80)
        self.assertSetEqual(set(prediction.alerts.values_list("type", flat=True)), {Alert.Type.PHYTOSANITARY, Alert.Type.CRITICAL, Alert.Type.ENVIRONMENTAL})

    def test_healthy_high_confidence_only_creates_environmental_alert(self):
        prediction, _ = processar_captura(self.capture_with_humidity(90), gerador=FixedRandom(), classe_prevista="Tomato___healthy", confianca=90)
        self.assertEqual(list(prediction.alerts.values_list("type", flat=True)), [Alert.Type.ENVIRONMENTAL])

    def test_processing_is_idempotent(self):
        capture = self.capture_with_humidity(60)
        first, first_created = processar_captura(capture, gerador=FixedRandom(), confianca=70)
        second, second_created = processar_captura(capture, gerador=FixedRandom(), confianca=90)
        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(capture.alerts.count(), 0)
