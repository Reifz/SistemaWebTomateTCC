import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("captures", "0002_nomes_em_portugues"),
        ("predictions", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RenameModel(old_name="Prediction", new_name="Predicao"),
                migrations.RenameField(model_name="predicao", old_name="capture", new_name="captura"),
                migrations.RenameField(model_name="predicao", old_name="predicted_class", new_name="classe_prevista"),
                migrations.RenameField(model_name="predicao", old_name="confidence", new_name="confianca"),
                migrations.RenameField(model_name="predicao", old_name="top_three", new_name="tres_principais"),
                migrations.RenameField(model_name="predicao", old_name="confidence_status", new_name="nivel_confianca"),
                migrations.RenameField(model_name="predicao", old_name="model_used", new_name="modelo_utilizado"),
                migrations.RenameField(model_name="predicao", old_name="predicted_at", new_name="prevista_em"),
                migrations.AlterModelTable(name="predicao", table="predictions_prediction"),
                migrations.AlterModelOptions(
                    name="predicao",
                    options={"ordering": ("-prevista_em",), "verbose_name": "predição", "verbose_name_plural": "predições"},
                ),
                migrations.AlterField(
                    model_name="predicao",
                    name="captura",
                    field=models.OneToOneField(
                        db_column="capture_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="predicao",
                        to="captures.captura",
                    ),
                ),
                migrations.AlterField(
                    model_name="predicao",
                    name="classe_prevista",
                    field=models.CharField(db_column="predicted_class", db_index=True, max_length=100, verbose_name="classe prevista"),
                ),
                migrations.AlterField(
                    model_name="predicao",
                    name="confianca",
                    field=models.DecimalField(
                        db_column="confidence",
                        decimal_places=2,
                        max_digits=5,
                        validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)],
                        verbose_name="confiança (%)",
                    ),
                ),
                migrations.AlterField(
                    model_name="predicao",
                    name="tres_principais",
                    field=models.JSONField(db_column="top_three", default=list, verbose_name="top 3"),
                ),
                migrations.AlterField(
                    model_name="predicao",
                    name="nivel_confianca",
                    field=models.CharField(
                        choices=[("alta", "Alta"), ("media", "Média"), ("baixa", "Baixa")],
                        db_column="confidence_status",
                        db_index=True,
                        max_length=8,
                        verbose_name="nível de confiança",
                    ),
                ),
                migrations.AlterField(
                    model_name="predicao",
                    name="modelo_utilizado",
                    field=models.CharField(db_column="model_used", default="MobileNetV2-mock-v1", max_length=100, verbose_name="modelo utilizado"),
                ),
                migrations.AlterField(
                    model_name="predicao",
                    name="prevista_em",
                    field=models.DateTimeField(auto_now_add=True, db_column="predicted_at", db_index=True, verbose_name="data/hora"),
                ),
            ],
        )
    ]
