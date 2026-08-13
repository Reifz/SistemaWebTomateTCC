from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class EnvironmentalReading(models.Model):
    capture = models.OneToOneField("captures.Capture", on_delete=models.CASCADE, related_name="environmental_reading", null=True, blank=True)
    temperature = models.DecimalField("temperatura (°C)", max_digits=5, decimal_places=2, validators=[MinValueValidator(-50), MaxValueValidator(80)])
    humidity = models.DecimalField("umidade (%)", max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    measured_at = models.DateTimeField("data/hora", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-measured_at",)
        verbose_name = "leitura ambiental"
        verbose_name_plural = "leituras ambientais"

    def __str__(self):
        return f"{self.temperature} °C / {self.humidity}%"
