from django.conf import settings
from django.db import models


class Captura(models.Model):
    class Origem(models.TextChoices):
        MANUAL = "manual", "Manual"

        SIMULADA = "simulado", "Simulado"

        ESP32 = "esp32", "ESP32-CAM"

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"

        PROCESSANDO = "processando", "Processando"

        PROCESSADA = "processada", "Processada"

        ERRO = "erro", "Erro"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="capturas",
        db_column="user_id",
    )

    imagem = models.ImageField("imagem", upload_to="captures/%Y/%m/", blank=True, db_column="image")

    capturada_em = models.DateTimeField("data/hora", auto_now_add=True, db_index=True, db_column="captured_at")

    origem = models.CharField(
        "origem",
        max_length=10,
        choices=Origem.choices,
        default=Origem.MANUAL,
        db_column="origin",
    )

    status = models.CharField(
        "status",
        max_length=12,
        choices=Status.choices,
        default=Status.PENDENTE,
        db_index=True,
    )

    observacao = models.TextField("observação", blank=True, db_column="observation")

    class Meta:
        db_table = "captures_capture"

        ordering = ("-capturada_em",)

        verbose_name = "captura"

        verbose_name_plural = "capturas"

    def __str__(self):
        return f"Captura #{self.pk} - {self.get_status_display()}"

    @property
    def rotulo_origem(self):
        return {
            self.Origem.SIMULADA: "Sistema",
            self.Origem.MANUAL: "Manual",
            self.Origem.ESP32: "Dispositivo",
        }.get(self.origem, self.origem)
