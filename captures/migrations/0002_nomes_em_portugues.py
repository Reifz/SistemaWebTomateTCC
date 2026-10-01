from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("captures", "0001_initial"),
        ("predictions", "0001_initial"),
        ("sensors", "0001_initial"),
        ("alerts", "0002_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RenameModel(old_name="Capture", new_name="Captura"),
                migrations.RenameField(model_name="captura", old_name="user", new_name="usuario"),
                migrations.RenameField(model_name="captura", old_name="image", new_name="imagem"),
                migrations.RenameField(model_name="captura", old_name="captured_at", new_name="capturada_em"),
                migrations.RenameField(model_name="captura", old_name="origin", new_name="origem"),
                migrations.RenameField(model_name="captura", old_name="observation", new_name="observacao"),
                migrations.AlterModelTable(name="captura", table="captures_capture"),
                migrations.AlterModelOptions(
                    name="captura",
                    options={"ordering": ("-capturada_em",), "verbose_name": "captura", "verbose_name_plural": "capturas"},
                ),
                migrations.AlterField(
                    model_name="captura",
                    name="usuario",
                    field=models.ForeignKey(
                        db_column="user_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="capturas",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                migrations.AlterField(
                    model_name="captura",
                    name="imagem",
                    field=models.ImageField(blank=True, db_column="image", upload_to="captures/%Y/%m/", verbose_name="imagem"),
                ),
                migrations.AlterField(
                    model_name="captura",
                    name="capturada_em",
                    field=models.DateTimeField(auto_now_add=True, db_column="captured_at", db_index=True, verbose_name="data/hora"),
                ),
                migrations.AlterField(
                    model_name="captura",
                    name="origem",
                    field=models.CharField(
                        choices=[("manual", "Manual"), ("simulado", "Simulado"), ("esp32", "ESP32-CAM")],
                        db_column="origin",
                        default="manual",
                        max_length=10,
                        verbose_name="origem",
                    ),
                ),
                migrations.AlterField(
                    model_name="captura",
                    name="observacao",
                    field=models.TextField(blank=True, db_column="observation", verbose_name="observação"),
                ),
            ],
        )
    ]
