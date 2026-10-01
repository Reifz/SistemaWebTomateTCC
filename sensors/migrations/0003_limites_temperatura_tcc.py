import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sensors", "0002_nomes_em_portugues")]

    operations = [
        migrations.AlterField(
            model_name="leituraambiental",
            name="temperatura",
            field=models.DecimalField(
                db_column="temperature",
                decimal_places=2,
                max_digits=5,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(60),
                ],
                verbose_name="temperatura (°C)",
            ),
        ),
    ]
