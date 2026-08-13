from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Prediction(models.Model):
    class ConfidenceStatus(models.TextChoices):
        HIGH = "alta", "Alta"
        MEDIUM = "media", "Média"
        LOW = "baixa", "Baixa"

    capture = models.OneToOneField("captures.Capture", on_delete=models.CASCADE, related_name="prediction")
    predicted_class = models.CharField("classe prevista", max_length=100, db_index=True)
    confidence = models.DecimalField("confiança (%)", max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    top_three = models.JSONField("top 3", default=list)
    confidence_status = models.CharField("nível de confiança", max_length=8, choices=ConfidenceStatus.choices, db_index=True)
    model_used = models.CharField("modelo utilizado", max_length=100, default="MobileNetV2-mock-v1")
    predicted_at = models.DateTimeField("data/hora", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-predicted_at",)
        verbose_name = "predição"
        verbose_name_plural = "predições"

    def clean(self):
        if not isinstance(self.top_three, list) or len(self.top_three) != 3:
            raise ValidationError({"top_three": "Informe exatamente três resultados."})

    def __str__(self):
        return f"{self.predicted_class} ({self.confidence}%)"
