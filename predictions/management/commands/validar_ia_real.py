import tempfile
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Valida os pesos e executa MobileSAM + MobileNetV2 em uma imagem real."

    def add_arguments(self, analisador):
        analisador.add_argument("--imagem", type=Path)

    def handle(self, *args, **opcoes):
        from predictions.inferencia import analisar

        caminho_imagem = opcoes.get("imagem")

        if caminho_imagem is None:
            pasta_amostras = Path(settings.BASE_DIR) / "fotos_nao_controladas"

            caminho_imagem = next(pasta_amostras.glob("*.jpg"), None)

        if caminho_imagem is None or not caminho_imagem.is_file():
            raise CommandError("Informe uma imagem JPEG existente com --imagem.")

        with tempfile.TemporaryDirectory() as pasta_temporaria:
            inicio = time.perf_counter()

            resultado = analisar(
                caminho_imagem,
                raiz_resultados=pasta_temporaria,
            )

            tempo_primeira_execucao_ms = (time.perf_counter() - inicio) * 1000

            inicio = time.perf_counter()

            resultado_aquecido = analisar(
                caminho_imagem,
                raiz_resultados=pasta_temporaria,
            )

            tempo_execucao_aquecida_ms = (time.perf_counter() - inicio) * 1000

        classificacao = resultado_aquecido.classificacao

        self.stdout.write(self.style.SUCCESS("Pipeline real executado com sucesso."))

        self.stdout.write(f"Imagem: {caminho_imagem}")

        self.stdout.write(f"Classe: {classificacao.classe_prevista}")

        self.stdout.write(f"Confiança: {classificacao.confianca_percentual:.2f}%")

        self.stdout.write(f"Pré-processamento: {resultado_aquecido.preprocessamento.status}")

        self.stdout.write(f"MobileNetV2: {classificacao.tempo_inferencia_ms} ms")

        self.stdout.write(f"MobileSAM: {resultado_aquecido.tempo_mobilesam_ms:.3f} ms")

        self.stdout.write(f"Primeira execução com carregamento: {tempo_primeira_execucao_ms:.3f} ms")

        self.stdout.write(f"Execução com modelos carregados: {tempo_execucao_aquecida_ms:.3f} ms")

        if classificacao.tempo_inferencia_ms > 3000:
            raise CommandError("A inferência da MobileNetV2 ultrapassou 3 segundos.")

        if tempo_execucao_aquecida_ms > 10000:
            raise CommandError("O fluxo completo com modelos carregados ultrapassou 10 segundos.")
