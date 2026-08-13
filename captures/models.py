from django.conf import settings
from django.db import models


class Capture(models.Model):
    class Origin(models.TextChoices):
        MANUAL = "manual", "Manual"
        SIMULATED = "simulado", "Simulado"
        ESP32 = "esp32", "ESP32-CAM"

    class Status(models.TextChoices):
        PENDING = "pendente", "Pendente"
        PROCESSED = "processada", "Processada"
        ERROR = "erro", "Erro"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="captures")
    image = models.ImageField("imagem", upload_to="captures/%Y/%m/", blank=True)
    captured_at = models.DateTimeField("data/hora", auto_now_add=True, db_index=True)
    origin = models.CharField("origem", max_length=10, choices=Origin.choices, default=Origin.MANUAL)
    status = models.CharField("status", max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    observation = models.TextField("observação", blank=True)

    class Meta:
        ordering = ("-captured_at",)
        verbose_name = "captura"
        verbose_name_plural = "capturas"

    def __str__(self):
        return f"Captura #{self.pk} - {self.get_status_display()}"

    @property
    def origin_label(self):
        return {self.Origin.SIMULATED: "Sistema", self.Origin.MANUAL: "Manual", self.Origin.ESP32: "Dispositivo"}.get(self.origin, self.origin)

    def get_origin_display(self):
        return self.origin_label
