from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("predictions", "0002_nomes_em_portugues")]

    operations = [
        migrations.AlterField(
            model_name="predicao",
            name="modelo_utilizado",
            field=models.CharField(db_column="model_used", default="MobileNetV2_Tomato_Modelo_B_v5", max_length=100, verbose_name="modelo utilizado"),
        ),
        migrations.AddField(
            model_name="predicao",
            name="id_execucao",
            field=models.CharField(blank=True, db_column="processing_id", max_length=24, null=True, unique=True, verbose_name="identificador da execução"),
        ),
        migrations.AddField(
            model_name="predicao",
            name="status_preprocessamento",
            field=models.CharField(blank=True, choices=[("segmentada", "Segmentada"), ("fallback_roi", "Recorte central")], db_column="preprocessing_status", max_length=12, verbose_name="status do pré-processamento"),
        ),
        migrations.AddField(
            model_name="predicao",
            name="caminho_imagem_processada",
            field=models.CharField(blank=True, db_column="processed_image_path", max_length=500, verbose_name="caminho da imagem processada"),
        ),
        migrations.AddField(
            model_name="predicao",
            name="caminho_imagem_guia",
            field=models.CharField(blank=True, db_column="guide_image_path", max_length=500, verbose_name="caminho da imagem com guia"),
        ),
        migrations.AddField(
            model_name="predicao",
            name="tempo_inferencia_ms",
            field=models.PositiveIntegerField(blank=True, db_column="mobilenet_time_ms", null=True, verbose_name="tempo de inferência da MobileNetV2 (ms)"),
        ),
        migrations.AddField(
            model_name="predicao",
            name="tempo_mobilesam_ms",
            field=models.DecimalField(blank=True, db_column="mobilesam_time_ms", decimal_places=3, max_digits=10, null=True, verbose_name="tempo do MobileSAM (ms)"),
        ),
        migrations.AddField(
            model_name="predicao",
            name="dispositivo_processamento",
            field=models.CharField(blank=True, db_column="processing_device", max_length=20, verbose_name="dispositivo de processamento"),
        ),
        migrations.AddField(
            model_name="predicao",
            name="motivos_fallback",
            field=models.JSONField(blank=True, db_column="fallback_reasons", default=list, verbose_name="motivos do recorte central"),
        ),
    ]
