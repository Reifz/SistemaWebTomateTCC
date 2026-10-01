from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("captures", "0002_nomes_em_portugues")]

    operations = [
        migrations.AlterField(
            model_name="captura",
            name="status",
            field=models.CharField(
                choices=[
                    ("pendente", "Pendente"),
                    ("processando", "Processando"),
                    ("processada", "Processada"),
                    ("erro", "Erro"),
                ],
                db_index=True,
                default="pendente",
                max_length=12,
                verbose_name="status",
            ),
        ),
    ]
