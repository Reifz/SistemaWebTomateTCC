from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class LeituraAmbiental(models.Model):
    dispositivo = models.ForeignKey(
        "devices.Dispositivo",
        on_delete=models.PROTECT,
        related_name="leituras_ambientais",
        db_column="device_id",
    )

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

    medida_em = models.DateTimeField("data/hora", auto_now_add=True, db_index=True, db_column="collected_at")

    status_validacao = models.CharField(
        "status de validação",
        max_length=7,
        choices=(("valid", "Válida"), ("invalid", "Inválida")),
        default="valid",
        db_column="validation_status",
    )

    criado_em = models.DateTimeField("criado em", auto_now_add=True, db_column="created_at")

    class Meta:
        db_table = "sensor_readings"

        ordering = ("-medida_em",)

        verbose_name = "leitura ambiental"

        verbose_name_plural = "leituras ambientais"

    def __str__(self):
        return f"{self.temperatura} °C / {self.umidade}%"

    def save(self, *args, **kwargs):
        if not self.dispositivo_id and self.captura_id:
            self.dispositivo_id = self.captura.dispositivo_id

        super().save(*args, **kwargs)
