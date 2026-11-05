from django.conf import settings
from django.db import models


class Dispositivo(models.Model):
    class Status(models.TextChoices):
        ATIVO = "active", "Ativo"
        INATIVO = "inactive", "Inativo"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="dispositivos",
        db_column="user_id",
        verbose_name="responsável",
    )
    identificador = models.CharField("identificador", max_length=100, unique=True, db_column="identifier")
    nome = models.CharField("nome", max_length=100, db_column="name")
    localizacao = models.CharField("localização", max_length=255, blank=True, null=True, db_column="location")
    status = models.CharField("situação", max_length=8, choices=Status.choices, default=Status.ATIVO)
    criado_em = models.DateTimeField("criado em", auto_now_add=True, db_column="created_at")
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True, null=True, db_column="updated_at")

    class Meta:
        db_table = "devices"
        ordering = ("nome", "identificador")
        verbose_name = "dispositivo"
        verbose_name_plural = "dispositivos"

    def save(self, *args, **kwargs):
        self.identificador = self.identificador.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nome} ({self.identificador})"


def obter_ou_criar_dispositivo_legado(usuario):
    """Define o dispositivo de registros antigos que não possuem identificador."""

    dispositivos = Dispositivo.objects.filter(usuario=usuario)
    ativos = dispositivos.filter(status=Dispositivo.Status.ATIVO)

    if ativos.count() == 1:
        return ativos.get()

    if ativos.exists():
        raise ValueError("Informe o dispositivo: o usuário possui mais de um dispositivo ativo.")

    if dispositivos.exists():
        raise ValueError("O usuário não possui dispositivo ativo.")

    dispositivo, _ = Dispositivo.objects.get_or_create(
        identificador=f"LEGACY-USER-{usuario.pk}",
        defaults={
            "usuario": usuario,
            "nome": "Dispositivo legado",
            "localizacao": "Registros anteriores à modelagem do TCC",
        },
    )

    return dispositivo
