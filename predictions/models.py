from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Predicao(models.Model):
    class NivelConfianca(models.TextChoices):
        ALTA = "alta", "Alta"

        MEDIA = "media", "Média"

        BAIXA = "baixa", "Baixa"

    class StatusPreprocessamento(models.TextChoices):
        SEGMENTADA = "segmentada", "Segmentada"

        FALLBACK_ROI = "fallback_roi", "Recorte central"

    captura = models.OneToOneField(
        "captures.Captura",
        on_delete=models.CASCADE,
        related_name="predicao",
        db_column="capture_id",
    )

    classe_prevista = models.CharField("classe prevista", max_length=100, db_index=True, db_column="predicted_class")

    confianca = models.DecimalField(
        "confiança (%)",
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        db_column="confidence",
    )

    tres_principais = models.JSONField("top 3", default=list, db_column="top_three")

    nivel_confianca = models.CharField(
        "nível de confiança",
        max_length=8,
        choices=NivelConfianca.choices,
        db_index=True,
        db_column="confidence_status",
    )

    modelo_utilizado = models.CharField(
        "modelo utilizado",
        max_length=100,
        default="MobileNetV2_Tomato_Modelo_B_v5",
        db_column="model_used",
    )

    id_execucao = models.CharField(
        "identificador da execução", max_length=24, unique=True, null=True, blank=True, db_column="processing_id"
    )

    status_preprocessamento = models.CharField(
        "status do pré-processamento", max_length=12, choices=StatusPreprocessamento.choices, blank=True, db_column="preprocessing_status"
    )

    caminho_imagem_processada = models.CharField(
        "caminho da imagem processada", max_length=500, blank=True, db_column="processed_image_path"
    )

    caminho_imagem_guia = models.CharField(
        "caminho da imagem com guia", max_length=500, blank=True, db_column="guide_image_path"
    )

    tempo_inferencia_ms = models.PositiveIntegerField(
        "tempo de inferência da MobileNetV2 (ms)", null=True, blank=True, db_column="mobilenet_time_ms"
    )

    tempo_mobilesam_ms = models.DecimalField(
        "tempo do MobileSAM (ms)", max_digits=10, decimal_places=3, null=True, blank=True, db_column="mobilesam_time_ms"
    )

    dispositivo_processamento = models.CharField(
        "dispositivo de processamento", max_length=20, blank=True, db_column="processing_device"
    )

    motivos_fallback = models.JSONField(
        "motivos do recorte central", default=list, blank=True, db_column="fallback_reasons"
    )

    prevista_em = models.DateTimeField("data/hora", auto_now_add=True, db_index=True, db_column="predicted_at")

    class Meta:
        db_table = "predictions_prediction"

        ordering = ("-prevista_em",)

        verbose_name = "predição"

        verbose_name_plural = "predições"

    def clean(self):
        if not isinstance(self.tres_principais, list) or len(self.tres_principais) != 3:
            raise ValidationError({"tres_principais": "Informe exatamente três resultados."})

    def __str__(self):
        return f"{self.classe_prevista} ({self.confianca}%)"

    @property
    def classe_amigavel(self):
        return self.classe_prevista.replace("Tomato___", "").replace("_", " ")
