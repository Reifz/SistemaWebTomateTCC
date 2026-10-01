from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class LeituraAmbiental(models.Model):
    captura = models.OneToOneField(
        "captures.Captura",
        on_delete=models.CASCADE,
        related_name="leitura_ambiental",
        null=True,
        blank=True,
        db_column="capture_id",
    )

    temperatura = models.DecimalField(
        "temperatura (°C)",
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(60)],
        db_column="temperature",
    )

    umidade = models.DecimalField(
        "umidade (%)",
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        db_column="humidity",
    )

    medida_em = models.DateTimeField("data/hora", auto_now_add=True, db_index=True, db_column="measured_at")

    class Meta:
        db_table = "sensors_environmentalreading"

        ordering = ("-medida_em",)

        verbose_name = "leitura ambiental"

        verbose_name_plural = "leituras ambientais"

    def __str__(self):
        return f"{self.temperatura} °C / {self.umidade}%"
