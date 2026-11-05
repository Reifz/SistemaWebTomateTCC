import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("alerts", "0004_alter_alerta_tipo"), ("predictions", "0004_alinhamento_tcc")]

    operations = [
        migrations.AlterModelTable(name="alerta", table="alerts"),
        migrations.AlterField(model_name="alerta", name="predicao", field=models.ForeignKey(blank=True, db_column="analysis_id", null=True, on_delete=django.db.models.deletion.CASCADE, related_name="alertas", to="predictions.predicao")),
        migrations.AlterField(model_name="alerta", name="tipo", field=models.CharField(choices=[("fitossanitario", "Fitossanitário"), ("baixa_confianca", "Baixa confiança"), ("ambiental", "Ambiental"), ("critico", "Crítico"), ("erro_leitura", "Erro de leitura")], db_column="alert_type", db_index=True, max_length=20, verbose_name="tipo")),
        migrations.AlterField(model_name="alerta", name="severidade", field=models.CharField(choices=[("baixa", "Baixa"), ("media", "Média"), ("alta", "Alta"), ("critica", "Crítica")], db_column="severity", db_index=True, max_length=8, verbose_name="severidade")),
        migrations.AlterField(model_name="alerta", name="visualizado", field=models.BooleanField(db_column="is_viewed", db_index=True, default=False, verbose_name="visualizado")),
    ]
