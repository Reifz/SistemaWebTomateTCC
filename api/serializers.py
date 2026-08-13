from rest_framework import serializers

from alerts.models import Alert
from captures.models import Capture
from predictions.models import Prediction


class EntradaCapturaSerializer(serializers.Serializer):
    # Contrato previsto para POST /api/captures/. O ESP32-CAM deverá enviar estes
    # campos como multipart/form-data.
    image = serializers.ImageField()
    observation = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    temperature = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=-50, max_value=80)
    humidity = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)


class EntradaPredicaoSerializer(serializers.Serializer):
    # Remova este serializer se a inferência for iniciada automaticamente.
    capture_id = serializers.IntegerField(min_value=1)


class AlertaSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)

    class Meta:
        model = Alert
        fields = ("id", "capture_id", "prediction_id", "type", "type_display", "severity", "severity_display", "message", "created_at", "viewed")


class PredicaoSerializer(serializers.ModelSerializer):
    alerts = AlertaSerializer(many=True, read_only=True)

    class Meta:
        model = Prediction
        fields = ("id", "capture_id", "predicted_class", "confidence", "confidence_status", "top_three", "model_used", "predicted_at", "alerts")


class CapturaSerializer(serializers.ModelSerializer):
    environmental_reading = serializers.SerializerMethodField()

    class Meta:
        model = Capture
        fields = ("id", "origin", "status", "observation", "captured_at", "environmental_reading")

    def get_environmental_reading(self, captura):
        leitura = getattr(captura, "environmental_reading", None)
        if not leitura:
            return None
        return {
            "temperature": leitura.temperature,
            "humidity": leitura.humidity,
            "measured_at": leitura.measured_at,
        }
