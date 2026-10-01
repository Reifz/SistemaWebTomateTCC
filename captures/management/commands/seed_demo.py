from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from captures.services import inserir_dados_demonstrativos


class Command(BaseCommand):
    help = "Cria dados demonstrativos para um usuário existente."

    def add_arguments(self, analisador):
        analisador.add_argument("--email", required=True)

        analisador.add_argument("--count", type=int, default=12)

    def handle(self, *argumentos, **opcoes):
        try:
            usuario = get_user_model().objects.get(email=opcoes["email"])
        except get_user_model().DoesNotExist as erro:
            raise CommandError("Usuário não encontrado. Crie-o antes com createsuperuser.") from erro

        inserir_dados_demonstrativos([usuario], opcoes["count"])

        self.stdout.write(self.style.SUCCESS(f"{opcoes['count']} capturas demonstrativas criadas."))
