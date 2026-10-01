import shutil
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from predictions.models import Predicao


class Command(BaseCommand):
    help = "Remove resultados inválidos após 30 dias e válidos após 90 dias."

    def add_arguments(self, analisador):
        analisador.add_argument(
            "--confirmar",
            action="store_true",
            help="Efetiva a remoção; sem esta opção o comando apenas lista.",
        )

    def handle(self, *args, **opcoes):
        confirmar = opcoes["confirmar"]

        raiz = Path(settings.RESULTS_ROOT).resolve()

        if not raiz.is_dir():
            self.stdout.write("A pasta de resultados ainda não existe.")

            return

        limite_validos = timezone.now() - timedelta(days=90)

        predicoes_expiradas = Predicao.objects.filter(
            prevista_em__lt=limite_validos,
            id_execucao__isnull=False,
        )

        ids_validos_expirados = set(
            predicoes_expiradas.values_list("id_execucao", flat=True)
        )

        limite_invalidos = timezone.now().timestamp() - timedelta(days=30).total_seconds()

        pastas_remover = []

        for pasta in raiz.iterdir():
            if not pasta.is_dir():
                continue

            erro = pasta / "erro.json"

            valido_expirado = pasta.name in ids_validos_expirados

            invalido_expirado = erro.is_file() and erro.stat().st_mtime < limite_invalidos

            if valido_expirado or invalido_expirado:
                pastas_remover.append(pasta.resolve())

        for pasta in pastas_remover:
            if not pasta.is_relative_to(raiz):
                raise CommandError(f"Caminho inseguro recusado: {pasta}")

            self.stdout.write(f"{'Removendo' if confirmar else 'Removeria'}: {pasta.name}")

            if confirmar:
                shutil.rmtree(pasta)

        if confirmar and ids_validos_expirados:
            predicoes_expiradas.update(
                caminho_imagem_processada="",
                caminho_imagem_guia="",
            )

        self.stdout.write(f"Total: {len(pastas_remover)} pasta(s).")
