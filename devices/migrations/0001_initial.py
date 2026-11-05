import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("accounts", "0002_alinhamento_tcc"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Dispositivo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("identificador", models.CharField(db_column="identifier", max_length=100, unique=True, verbose_name="identificador")),
                ("nome", models.CharField(db_column="name", max_length=100, verbose_name="nome")),
                ("localizacao", models.CharField(blank=True, db_column="location", max_length=255, null=True, verbose_name="localização")),
                ("status", models.CharField(choices=[("active", "Ativo"), ("inactive", "Inativo")], default="active", max_length=8, verbose_name="situação")),
                ("criado_em", models.DateTimeField(auto_now_add=True, db_column="created_at", verbose_name="criado em")),
                ("atualizado_em", models.DateTimeField(auto_now=True, db_column="updated_at", null=True, verbose_name="atualizado em")),
                ("usuario", models.ForeignKey(db_column="user_id", on_delete=django.db.models.deletion.PROTECT, related_name="dispositivos", to=settings.AUTH_USER_MODEL, verbose_name="responsável")),
            ],
            options={"db_table": "devices", "ordering": ("nome", "identificador"), "verbose_name": "dispositivo", "verbose_name_plural": "dispositivos"},
        )
    ]
