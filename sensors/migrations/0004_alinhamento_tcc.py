import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone


def preencher_leituras(apps, schema_editor):
    Leitura = apps.get_model("sensors", "LeituraAmbiental")

    for leitura in Leitura.objects.select_related("captura").all().iterator():
        Leitura.objects.filter(pk=leitura.pk).update(
            dispositivo_id=leitura.captura.dispositivo_id,
            status_validacao="valid",
            criado_em=leitura.medida_em,
        )


class Migration(migrations.Migration):
    dependencies = [("sensors", "0003_limites_temperatura_tcc"), ("captures", "0004_alinhamento_tcc"), ("devices", "0001_initial")]

    operations = [
        migrations.AlterModelTable(name="leituraambiental", table="sensor_readings"),
        migrations.AlterField(model_name="leituraambiental", name="medida_em", field=models.DateTimeField(auto_now_add=True, db_column="collected_at", db_index=True, verbose_name="data/hora")),
        migrations.AddField(model_name="leituraambiental", name="dispositivo", field=models.ForeignKey(db_column="device_id", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="leituras_ambientais", to="devices.dispositivo")),
        migrations.AddField(model_name="leituraambiental", name="status_validacao", field=models.CharField(choices=[("valid", "Válida"), ("invalid", "Inválida")], db_column="validation_status", default="valid", max_length=7, verbose_name="status de validação")),
        migrations.AddField(model_name="leituraambiental", name="criado_em", field=models.DateTimeField(db_column="created_at", default=timezone.now, verbose_name="criado em"), preserve_default=False),
        migrations.RunPython(preencher_leituras, migrations.RunPython.noop),
        migrations.AlterField(model_name="leituraambiental", name="dispositivo", field=models.ForeignKey(db_column="device_id", on_delete=django.db.models.deletion.PROTECT, related_name="leituras_ambientais", to="devices.dispositivo")),
        migrations.AlterField(model_name="leituraambiental", name="criado_em", field=models.DateTimeField(auto_now_add=True, db_column="created_at", verbose_name="criado em")),
    ]
