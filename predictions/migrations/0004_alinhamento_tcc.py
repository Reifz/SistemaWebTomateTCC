import django.core.validators
import django.db.models.deletion
from decimal import Decimal

from django.db import migrations, models
from django.utils import timezone


def preencher_analises(apps, schema_editor):
    Analise = apps.get_model("predictions", "Predicao")
    ResultadoIA = apps.get_model("predictions", "ResultadoIA")
    for analise in Analise.objects.select_related("captura").all().iterator():
        leitura = getattr(analise.captura, "leitura_ambiental", None)
        Analise.objects.filter(pk=analise.pk).update(
            dispositivo_id=analise.captura.dispositivo_id,
            leitura_ambiental_id=leitura.pk if leitura else None,
            tempo_inferencia_ms=analise.tempo_inferencia_ms or 0,
            criado_em=analise.prevista_em,
        )

        ResultadoIA.objects.bulk_create(
            [
                ResultadoIA(
                    analise_id=analise.pk,
                    nome_classe=item.get("class", ""),
                    probabilidade=Decimal(str(item.get("confidence", 0))).quantize(Decimal("0.01")),
                    posicao=posicao,
                    criado_em=analise.prevista_em,
                )
                for posicao, item in enumerate(analise.tres_principais[:3], start=1)
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("predictions", "0003_integracao_ia_real"),
        ("captures", "0004_alinhamento_tcc"),
        ("sensors", "0004_alinhamento_tcc"),
        ("devices", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelTable(name="predicao", table="analyses"),
        migrations.AlterField(model_name="predicao", name="captura", field=models.OneToOneField(db_column="image_id", on_delete=django.db.models.deletion.CASCADE, related_name="predicao", to="captures.captura")),
        migrations.AlterField(model_name="predicao", name="confianca", field=models.DecimalField(db_column="main_probability", decimal_places=2, max_digits=5, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)], verbose_name="confiança (%)")),
        migrations.AlterField(model_name="predicao", name="prevista_em", field=models.DateTimeField(auto_now_add=True, db_column="analyzed_at", db_index=True, verbose_name="data/hora")),
        migrations.AddField(model_name="predicao", name="dispositivo", field=models.ForeignKey(db_column="device_id", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="analises", to="devices.dispositivo")),
        migrations.AddField(model_name="predicao", name="leitura_ambiental", field=models.OneToOneField(blank=True, db_column="sensor_reading_id", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="analise", to="sensors.leituraambiental")),
        migrations.AddField(model_name="predicao", name="criado_em", field=models.DateTimeField(db_column="created_at", default=timezone.now, verbose_name="criado em"), preserve_default=False),
        migrations.CreateModel(
            name="ResultadoIA",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome_classe", models.CharField(db_column="class_name", max_length=100, verbose_name="classe")),
                ("probabilidade", models.DecimalField(db_column="probability", decimal_places=2, max_digits=5, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)], verbose_name="probabilidade (%)")),
                ("posicao", models.PositiveSmallIntegerField(db_column="rank", verbose_name="posição")),
                ("criado_em", models.DateTimeField(auto_now_add=True, db_column="created_at", verbose_name="criado em")),
                ("analise", models.ForeignKey(db_column="analysis_id", on_delete=django.db.models.deletion.CASCADE, related_name="resultados_ia", to="predictions.predicao")),
            ],
            options={
                "db_table": "ai_results",
                "ordering": ("posicao",),
                "constraints": [
                    models.UniqueConstraint(fields=("analise", "posicao"), name="unique_ai_result_rank"),
                    models.CheckConstraint(condition=models.Q(("posicao__gte", 1), ("posicao__lte", 3)), name="ai_result_rank_between_1_3"),
                    models.CheckConstraint(condition=models.Q(("probabilidade__gte", 0), ("probabilidade__lte", 100)), name="ai_probability_between_0_100"),
                ],
            },
        ),
        migrations.RunPython(preencher_analises, migrations.RunPython.noop),
        migrations.AlterField(model_name="predicao", name="tempo_inferencia_ms", field=models.PositiveIntegerField(db_column="inference_time_ms", default=0, verbose_name="tempo de inferência da MobileNetV2 (ms)")),
        migrations.AlterField(model_name="predicao", name="dispositivo", field=models.ForeignKey(db_column="device_id", on_delete=django.db.models.deletion.PROTECT, related_name="analises", to="devices.dispositivo")),
        migrations.AlterField(model_name="predicao", name="criado_em", field=models.DateTimeField(auto_now_add=True, db_column="created_at", verbose_name="criado em")),
        migrations.AddConstraint(model_name="predicao", constraint=models.CheckConstraint(condition=models.Q(("confianca__gte", 0), ("confianca__lte", 100)), name="main_probability_between_0_100")),
    ]
