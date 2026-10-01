from django.db import migrations, models
import django.db.models.deletion


MAPEAMENTO_MODELOS = (
    ("captures", "capture", "captura"),
    ("predictions", "prediction", "predicao"),
    ("sensors", "environmentalreading", "leituraambiental"),
    ("alerts", "alert", "alerta"),
)


def atualizar_tipos_conteudo_e_permissoes(aplicativos, editor_esquema):
    TipoConteudo = aplicativos.get_model("contenttypes", "ContentType")
    Permissao = aplicativos.get_model("auth", "Permission")

    for rotulo_aplicativo, nome_antigo, nome_novo in MAPEAMENTO_MODELOS:
        tipo_conteudo = TipoConteudo.objects.filter(app_label=rotulo_aplicativo, model=nome_antigo).first()
        if not tipo_conteudo:
            continue

        for permissao in Permissao.objects.filter(content_type=tipo_conteudo):
            acao, separador, modelo = permissao.codename.partition("_")
            if separador and modelo == nome_antigo:
                permissao.codename = f"{acao}_{nome_novo}"
                permissao.save(update_fields=["codename"])

        tipo_conteudo.model = nome_novo
        tipo_conteudo.save(update_fields=["model"])


def restaurar_tipos_conteudo_e_permissoes(aplicativos, editor_esquema):
    TipoConteudo = aplicativos.get_model("contenttypes", "ContentType")
    Permissao = aplicativos.get_model("auth", "Permission")

    for rotulo_aplicativo, nome_antigo, nome_novo in MAPEAMENTO_MODELOS:
        tipo_conteudo = TipoConteudo.objects.filter(app_label=rotulo_aplicativo, model=nome_novo).first()
        if not tipo_conteudo:
            continue

        for permissao in Permissao.objects.filter(content_type=tipo_conteudo):
            acao, separador, modelo = permissao.codename.partition("_")
            if separador and modelo == nome_novo:
                permissao.codename = f"{acao}_{nome_antigo}"
                permissao.save(update_fields=["codename"])

        tipo_conteudo.model = nome_antigo
        tipo_conteudo.save(update_fields=["model"])


class Migration(migrations.Migration):
    dependencies = [
        ("alerts", "0002_initial"),
        ("captures", "0002_nomes_em_portugues"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("predictions", "0002_nomes_em_portugues"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RenameModel(old_name="Alert", new_name="Alerta"),
                migrations.RenameField(model_name="alerta", old_name="capture", new_name="captura"),
                migrations.RenameField(model_name="alerta", old_name="prediction", new_name="predicao"),
                migrations.RenameField(model_name="alerta", old_name="type", new_name="tipo"),
                migrations.RenameField(model_name="alerta", old_name="severity", new_name="severidade"),
                migrations.RenameField(model_name="alerta", old_name="message", new_name="mensagem"),
                migrations.RenameField(model_name="alerta", old_name="created_at", new_name="criado_em"),
                migrations.RenameField(model_name="alerta", old_name="viewed", new_name="visualizado"),
                migrations.AlterModelTable(name="alerta", table="alerts_alert"),
                migrations.AlterModelOptions(
                    name="alerta",
                    options={"ordering": ("-criado_em",), "verbose_name": "alerta", "verbose_name_plural": "alertas"},
                ),
                migrations.AlterField(
                    model_name="alerta",
                    name="captura",
                    field=models.ForeignKey(
                        blank=True,
                        db_column="capture_id",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="alertas",
                        to="captures.captura",
                    ),
                ),
                migrations.AlterField(
                    model_name="alerta",
                    name="predicao",
                    field=models.ForeignKey(
                        blank=True,
                        db_column="prediction_id",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="alertas",
                        to="predictions.predicao",
                    ),
                ),
                migrations.AlterField(
                    model_name="alerta",
                    name="tipo",
                    field=models.CharField(
                        choices=[("fitossanitario", "Fitossanitário"), ("baixa_confianca", "Baixa confiança"), ("ambiental", "Ambiental"), ("critico", "Crítico")],
                        db_column="type",
                        db_index=True,
                        max_length=20,
                        verbose_name="tipo",
                    ),
                ),
                migrations.AlterField(
                    model_name="alerta",
                    name="severidade",
                    field=models.CharField(
                        choices=[("baixa", "Baixa"), ("media", "Média"), ("alta", "Alta"), ("critica", "Crítica")],
                        db_column="severity",
                        db_index=True,
                        max_length=8,
                        verbose_name="severidade",
                    ),
                ),
                migrations.AlterField(
                    model_name="alerta",
                    name="mensagem",
                    field=models.TextField(db_column="message", verbose_name="mensagem"),
                ),
                migrations.AlterField(
                    model_name="alerta",
                    name="criado_em",
                    field=models.DateTimeField(auto_now_add=True, db_column="created_at", db_index=True, verbose_name="data/hora"),
                ),
                migrations.AlterField(
                    model_name="alerta",
                    name="visualizado",
                    field=models.BooleanField(db_column="viewed", db_index=True, default=False, verbose_name="visualizado"),
                ),
            ],
        ),
        migrations.RunPython(
            atualizar_tipos_conteudo_e_permissoes,
            restaurar_tipos_conteudo_e_permissoes,
        ),
    ]
