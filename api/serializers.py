from rest_framework import serializers
from django.urls import reverse

from alerts.models import Alerta
from captures.models import Captura
from predictions.models import Predicao


class SerializadorEntradaCaptura(serializers.Serializer):
    # Contrato previsto para POST /api/captures/. O ESP32-CAM deverá enviar estes
    # campos como multipart/form-data.
    image = serializers.ImageField()

    observation = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    temperature = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=60)

    humidity = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)

    def validate_image(self, imagem):
        if getattr(imagem, "content_type", "") not in ("image/jpeg", "image/jpg"):
            raise serializers.ValidationError("Envie uma imagem JPEG ou JPG.")

        return imagem


class SerializadorEntradaPredicao(serializers.Serializer):
    # Contrato do acionamento manual da inferência por uma captura existente.
    capture_id = serializers.IntegerField(min_value=1)


class SerializadorAlerta(serializers.ModelSerializer):
    capture_id = serializers.IntegerField(source="captura_id", read_only=True)

    prediction_id = serializers.IntegerField(source="predicao_id", read_only=True)

    type = serializers.CharField(source="tipo", read_only=True)

    type_display = serializers.CharField(source="get_tipo_display", read_only=True)

    severity = serializers.CharField(source="severidade", read_only=True)

    severity_display = serializers.CharField(source="get_severidade_display", read_only=True)

    message = serializers.CharField(source="mensagem", read_only=True)

    created_at = serializers.DateTimeField(source="criado_em", read_only=True)

    viewed = serializers.BooleanField(source="visualizado", read_only=True)

    class Meta:
        model = Alerta

        fields = ("id", "capture_id", "prediction_id", "type", "type_display", "severity", "severity_display", "message", "created_at", "viewed")


class SerializadorPredicao(serializers.ModelSerializer):
    capture_id = serializers.IntegerField(source="captura_id", read_only=True)

    predicted_class = serializers.CharField(source="classe_prevista", read_only=True)

    confidence = serializers.DecimalField(source="confianca", max_digits=5, decimal_places=2, read_only=True)

    confidence_status = serializers.CharField(source="nivel_confianca", read_only=True)

    top_three = serializers.JSONField(source="tres_principais", read_only=True)

    model_used = serializers.CharField(source="modelo_utilizado", read_only=True)

    predicted_at = serializers.DateTimeField(source="prevista_em", read_only=True)

    alerts = SerializadorAlerta(source="alertas", many=True, read_only=True)

    processing_id = serializers.CharField(source="id_execucao", read_only=True)

    preprocessing_status = serializers.CharField(source="status_preprocessamento", read_only=True)

    inference_time_ms = serializers.IntegerField(source="tempo_inferencia_ms", read_only=True)

    mobilesam_time_ms = serializers.DecimalField(source="tempo_mobilesam_ms", max_digits=10, decimal_places=3, read_only=True)

    processing_device = serializers.CharField(source="dispositivo_processamento", read_only=True)

    fallback_reasons = serializers.JSONField(source="motivos_fallback", read_only=True)

    processed_image_url = serializers.SerializerMethodField()

    guide_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Predicao

        fields = (
            "id",
            "capture_id",
            "predicted_class",
            "confidence",
            "confidence_status",
            "top_three",
            "model_used",
            "predicted_at",
            "processing_id",
            "preprocessing_status",
            "inference_time_ms",
            "mobilesam_time_ms",
            "processing_device",
            "fallback_reasons",
            "processed_image_url",
            "guide_image_url",
            "alerts",
        )

    def _url_artefato(self, predicao, tipo, disponivel):
        if not disponivel:
            return None

        caminho = reverse("api_artefato_predicao", args=(predicao.pk, tipo))

        requisicao = self.context.get("request")

        return requisicao.build_absolute_uri(caminho) if requisicao else caminho

    def get_processed_image_url(self, predicao):
        return self._url_artefato(
            predicao,
            "processed",
            predicao.caminho_imagem_processada,
        )

    def get_guide_image_url(self, predicao):
        return self._url_artefato(
            predicao,
            "guide",
            predicao.caminho_imagem_guia,
        )


class SerializadorCaptura(serializers.ModelSerializer):
    origin = serializers.CharField(source="origem", read_only=True)

    observation = serializers.CharField(source="observacao", read_only=True)

    captured_at = serializers.DateTimeField(source="capturada_em", read_only=True)

    environmental_reading = serializers.SerializerMethodField(method_name="obter_leitura_ambiental")

    class Meta:
        model = Captura

        fields = ("id", "origin", "status", "observation", "captured_at", "environmental_reading")

    def obter_leitura_ambiental(self, captura):
        leitura = getattr(captura, "leitura_ambiental", None)

        if not leitura:
            return None

        return {
            "temperature": leitura.temperatura,
            "humidity": leitura.umidade,
            "measured_at": leitura.medida_em,
        }
