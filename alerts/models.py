from django.core.exceptions import ValidationError
from django.db import models


class Alerta(models.Model):
    class Tipo(models.TextChoices):
        FITOSSANITARIO = "fitossanitario", "Fitossanitário"

        BAIXA_CONFIANCA = "baixa_confianca", "Baixa confiança"

        AMBIENTAL = "ambiental", "Ambiental"

        CRITICO = "critico", "Crítico"

    class Severidade(models.TextChoices):
        BAIXA = "baixa", "Baixa"

        MEDIA = "media", "Média"

        ALTA = "alta", "Alta"

        CRITICA = "critica", "Crítica"

    captura = models.ForeignKey(
        "captures.Captura",
        on_delete=models.CASCADE,
        related_name="alertas",
        null=True,
        blank=True,
        db_column="capture_id",
    )

    predicao = models.ForeignKey(
        "predictions.Predicao",
        on_delete=models.CASCADE,
        related_name="alertas",
        null=True,
        blank=True,
        db_column="prediction_id",
    )

    tipo = models.CharField("tipo", max_length=20, choices=Tipo.choices, db_index=True, db_column="type")

    severidade = models.CharField(
        "severidade", max_length=8, choices=Severidade.choices, db_index=True, db_column="severity"
    )

    mensagem = models.TextField("mensagem", db_column="message")

    criado_em = models.DateTimeField("data/hora", auto_now_add=True, db_index=True, db_column="created_at")

    visualizado = models.BooleanField("visualizado", default=False, db_index=True, db_column="viewed")

    class Meta:
        db_table = "alerts_alert"

        ordering = ("-criado_em",)

        verbose_name = "alerta"

        verbose_name_plural = "alertas"

    def clean(self):
        if not self.captura_id and not self.predicao_id:
            raise ValidationError("O alerta deve estar ligado a uma captura ou predição.")

    @property
    def proprietario(self):
        return self.captura.usuario if self.captura_id else self.predicao.captura.usuario

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.get_severidade_display()}"
