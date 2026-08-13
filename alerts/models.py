from django.core.exceptions import ValidationError
from django.db import models


class Alert(models.Model):
    class Type(models.TextChoices):
        PHYTOSANITARY = "fitossanitario", "Fitossanitário"
        LOW_CONFIDENCE = "baixa_confianca", "Baixa confiança"
        ENVIRONMENTAL = "ambiental", "Ambiental"
        CRITICAL = "critico", "Crítico"

    class Severity(models.TextChoices):
        LOW = "baixa", "Baixa"
        MEDIUM = "media", "Média"
        HIGH = "alta", "Alta"
        CRITICAL = "critica", "Crítica"

    capture = models.ForeignKey("captures.Capture", on_delete=models.CASCADE, related_name="alerts", null=True, blank=True)
    prediction = models.ForeignKey("predictions.Prediction", on_delete=models.CASCADE, related_name="alerts", null=True, blank=True)
    type = models.CharField("tipo", max_length=20, choices=Type.choices, db_index=True)
    severity = models.CharField("severidade", max_length=8, choices=Severity.choices, db_index=True)
    message = models.TextField("mensagem")
    created_at = models.DateTimeField("data/hora", auto_now_add=True, db_index=True)
    viewed = models.BooleanField("visualizado", default=False, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "alerta"
        verbose_name_plural = "alertas"

    def clean(self):
        if not self.capture_id and not self.prediction_id:
            raise ValidationError("O alerta deve estar ligado a uma captura ou predição.")

    @property
    def owner(self):
        return self.capture.user if self.capture_id else self.prediction.capture.user

    def __str__(self):
        return f"{self.get_type_display()} - {self.get_severity_display()}"
