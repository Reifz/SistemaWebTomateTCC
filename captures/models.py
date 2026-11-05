from pathlib import Path

from django.conf import settings
from django.db import models
from PIL import Image, UnidentifiedImageError


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

    dispositivo = models.ForeignKey(
        "devices.Dispositivo",
        on_delete=models.PROTECT,
        related_name="imagens",
        db_column="device_id",
    )

    imagem = models.ImageField("imagem", upload_to="captures/%Y/%m/", blank=True, db_column="file_path", max_length=500)

    formato_arquivo = models.CharField("formato", max_length=20, default="JPEG", db_column="file_format")

    resolucao_original = models.CharField(
        "resolução original", max_length=30, null=True, blank=True, db_column="original_resolution"
    )

    status_validacao = models.CharField(
        "status de validação",
        max_length=7,
        choices=(("valid", "Válida"), ("invalid", "Inválida")),
        default="valid",
        db_column="validation_status",
    )

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

    criado_em = models.DateTimeField("criado em", auto_now_add=True, db_column="created_at")

    class Meta:
        db_table = "images"

        ordering = ("-capturada_em",)

        verbose_name = "captura"

        verbose_name_plural = "capturas"

    def __str__(self):
        return f"Captura #{self.pk} - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        nova_captura = self._state.adding

        campos_atualizados = kwargs.get("update_fields")

        imagem_alterada = (
            campos_atualizados is None
            or "imagem" in campos_atualizados
        )

        if not self.dispositivo_id and self.usuario_id:
            from devices.models import obter_ou_criar_dispositivo_legado

            self.dispositivo = obter_ou_criar_dispositivo_legado(self.usuario)

        super().save(*args, **kwargs)

        if not self.imagem or not (
            nova_captura or imagem_alterada or not self.resolucao_original
        ):
            return

        formato = Path(self.imagem.name).suffix.lstrip(".").upper() or "JPEG"

        if formato == "JPG":
            formato = "JPEG"

        try:
            self.imagem.open("rb")

            with Image.open(self.imagem) as imagem:
                resolucao = f"{imagem.width}x{imagem.height}"
        except (FileNotFoundError, OSError, UnidentifiedImageError, ValueError):
            return
        finally:
            self.imagem.close()

        self.formato_arquivo = formato

        self.resolucao_original = resolucao

        type(self).objects.filter(pk=self.pk).update(
            formato_arquivo=formato,
            resolucao_original=resolucao,
        )

    @property
    def rotulo_origem(self):
        return {
            self.Origem.SIMULADA: "Sistema",
            self.Origem.MANUAL: "Manual",
            self.Origem.ESP32: "Dispositivo",
        }.get(self.origem, self.origem)
