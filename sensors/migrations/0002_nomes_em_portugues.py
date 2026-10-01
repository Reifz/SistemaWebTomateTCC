import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("captures", "0002_nomes_em_portugues"),
        ("sensors", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RenameModel(old_name="EnvironmentalReading", new_name="LeituraAmbiental"),
                migrations.RenameField(model_name="leituraambiental", old_name="capture", new_name="captura"),
                migrations.RenameField(model_name="leituraambiental", old_name="temperature", new_name="temperatura"),
                migrations.RenameField(model_name="leituraambiental", old_name="humidity", new_name="umidade"),
                migrations.RenameField(model_name="leituraambiental", old_name="measured_at", new_name="medida_em"),
                migrations.AlterModelTable(name="leituraambiental", table="sensors_environmentalreading"),
                migrations.AlterModelOptions(
                    name="leituraambiental",
                    options={"ordering": ("-medida_em",), "verbose_name": "leitura ambiental", "verbose_name_plural": "leituras ambientais"},
                ),
                migrations.AlterField(
                    model_name="leituraambiental",
                    name="captura",
                    field=models.OneToOneField(
                        blank=True,
                        db_column="capture_id",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="leitura_ambiental",
                        to="captures.captura",
                    ),
                ),
                migrations.AlterField(
                    model_name="leituraambiental",
                    name="temperatura",
                    field=models.DecimalField(
                        db_column="temperature",
                        decimal_places=2,
                        max_digits=5,
                        validators=[django.core.validators.MinValueValidator(-50), django.core.validators.MaxValueValidator(80)],
                        verbose_name="temperatura (°C)",
                    ),
                ),
                migrations.AlterField(
                    model_name="leituraambiental",
                    name="umidade",
                    field=models.DecimalField(
                        db_column="humidity",
                        decimal_places=2,
                        max_digits=5,
                        validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)],
                        verbose_name="umidade (%)",
                    ),
                ),
                migrations.AlterField(
                    model_name="leituraambiental",
                    name="medida_em",
                    field=models.DateTimeField(auto_now_add=True, db_column="measured_at", db_index=True, verbose_name="data/hora"),
                ),
            ],
        )
    ]
