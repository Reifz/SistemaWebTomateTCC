from django.db import migrations, models
from django.utils import timezone


def preencher_usuario_tcc(apps, schema_editor):
    Usuario = apps.get_model("accounts", "User")

    for usuario in Usuario.objects.all().iterator():
        nome = f"{usuario.first_name} {usuario.last_name}".strip() or usuario.email
        Usuario.objects.filter(pk=usuario.pk).update(
            nome=nome,
            perfil="admin" if usuario.is_staff else "user",
        )


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]

    operations = [
        migrations.AlterModelOptions(name="user", options={}),
        migrations.AlterModelTable(name="user", table="users"),
        migrations.AlterField(
            model_name="user",
            name="date_joined",
            field=models.DateTimeField(db_column="created_at", default=timezone.now, verbose_name="data de cadastro"),
        ),
        migrations.AddField(
            model_name="user",
            name="nome",
            field=models.CharField(db_column="name", default="", max_length=150, verbose_name="nome"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="user",
            name="perfil",
            field=models.CharField(choices=[("admin", "Administrador"), ("user", "Usuário")], db_column="role", db_index=True, default="user", max_length=5, verbose_name="perfil"),
        ),
        migrations.AddField(
            model_name="user",
            name="atualizado_em",
            field=models.DateTimeField(auto_now=True, db_column="updated_at", null=True, verbose_name="data de atualização"),
        ),
        migrations.RunPython(preencher_usuario_tcc, migrations.RunPython.noop),
    ]
