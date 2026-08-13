from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from captures.services import inserir_dados_demonstrativos


class Command(BaseCommand):
    help = "Cria dados demonstrativos para um usuário existente."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--count", type=int, default=12)

    def handle(self, *args, **options):
        try:
            user = get_user_model().objects.get(email=options["email"])
        except get_user_model().DoesNotExist as exc:
            raise CommandError("Usuário não encontrado. Crie-o antes com createsuperuser.") from exc
        inserir_dados_demonstrativos([user], options["count"])
        self.stdout.write(self.style.SUCCESS(f"{options['count']} capturas demonstrativas criadas."))
