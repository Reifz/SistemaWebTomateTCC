from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("alerts", "0003_nomes_em_portugues")]

    operations = [
        migrations.AlterField(
            model_name="alerta",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("fitossanitario", "Fitossanitário"),
                    ("baixa_confianca", "Baixa confiança"),
                    ("ambiental", "Ambiental"),
                    ("critico", "Crítico"),
                    ("erro_leitura", "Erro de leitura"),
                ],
                db_column="type",
                db_index=True,
                max_length=20,
                verbose_name="tipo",
            ),
        ),
    ]
