import django.db.models.deletion
from pathlib import Path

from django.db import migrations, models
from django.utils import timezone
from PIL import Image, UnidentifiedImageError


def vincular_dispositivos(apps, schema_editor):
    Captura = apps.get_model("captures", "Captura")
    Dispositivo = apps.get_model("devices", "Dispositivo")

    for captura in Captura.objects.select_related("usuario").all().iterator():
        formato = Path(captura.imagem.name).suffix.lstrip(".").upper() or "JPEG"

        if formato == "JPG":
            formato = "JPEG"

        resolucao = None

        try:
            with Image.open(captura.imagem.path) as imagem:
                resolucao = f"{imagem.width}x{imagem.height}"
        except (FileNotFoundError, OSError, UnidentifiedImageError, ValueError):
            pass

        dispositivo, _ = Dispositivo.objects.get_or_create(
            identificador=f"LEGACY-USER-{captura.usuario_id}",
            defaults={
                "usuario_id": captura.usuario_id,
                "nome": "Dispositivo legado",
                "localizacao": "Registros anteriores à modelagem do TCC",
                "status": "active",
            },
        )
        Captura.objects.filter(pk=captura.pk).update(
            dispositivo_id=dispositivo.pk,
            formato_arquivo=formato,
            resolucao_original=resolucao,
            status_validacao="valid",
            criado_em=captura.capturada_em,
        )


class Migration(migrations.Migration):
    dependencies = [("captures", "0003_estado_processando"), ("devices", "0001_initial")]

    operations = [
        migrations.AlterModelTable(name="captura", table="images"),
        migrations.AlterField(model_name="captura", name="imagem", field=models.ImageField(blank=True, db_column="file_path", max_length=500, upload_to="captures/%Y/%m/", verbose_name="imagem")),
        migrations.AddField(model_name="captura", name="formato_arquivo", field=models.CharField(db_column="file_format", default="JPEG", max_length=20, verbose_name="formato")),
        migrations.AddField(model_name="captura", name="resolucao_original", field=models.CharField(blank=True, db_column="original_resolution", max_length=30, null=True, verbose_name="resolução original")),
        migrations.AddField(model_name="captura", name="status_validacao", field=models.CharField(choices=[("valid", "Válida"), ("invalid", "Inválida")], db_column="validation_status", default="valid", max_length=7, verbose_name="status de validação")),
        migrations.AddField(model_name="captura", name="criado_em", field=models.DateTimeField(db_column="created_at", default=timezone.now, verbose_name="criado em"), preserve_default=False),
        migrations.AddField(model_name="captura", name="dispositivo", field=models.ForeignKey(db_column="device_id", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="imagens", to="devices.dispositivo")),
        migrations.RunPython(vincular_dispositivos, migrations.RunPython.noop),
        migrations.AlterField(model_name="captura", name="dispositivo", field=models.ForeignKey(db_column="device_id", on_delete=django.db.models.deletion.PROTECT, related_name="imagens", to="devices.dispositivo")),
        migrations.AlterField(model_name="captura", name="criado_em", field=models.DateTimeField(auto_now_add=True, db_column="created_at", verbose_name="criado em")),
    ]
