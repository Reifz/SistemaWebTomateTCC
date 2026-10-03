import tempfile
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from alerts.models import Alerta
from captures.models import Captura
from predictions.services import gerar_leitura_ambiental, nivel_confianca, processar_captura


class TestesServicoPredicao(TestCase):
    """
    Suíte de testes de integração e unidade para o serviço de predição (`processar_captura`).
    Valida regras de negócio para geração de alertas, idempotência do processamento,
    mapeamento de níveis de confiança e persistência de dados de inferência.
    """

    def setUp(self):
        """
        Configura o ambiente de testes criando diretórios temporários para os arquivos
        de mídia (`MEDIA_ROOT`) e resultados das inferências (`RESULTS_ROOT`).
        """
        self.pasta_midia = tempfile.TemporaryDirectory()

        self.pasta_resultados = tempfile.TemporaryDirectory()

        # Sobrescreve as configurações de caminhos de arquivos para isolar os testes do ambiente real
        self.configuracoes = override_settings(
            MEDIA_ROOT=self.pasta_midia.name,
            RESULTS_ROOT=self.pasta_resultados.name,
        )

        self.configuracoes.enable()

        self.usuario = get_user_model().objects.create_user(
            email="test@example.com",
            password="test-pass-123",
        )

        self.quantidade_execucoes = 0

    def tearDown(self):
        """
        Limpa os diretórios temporários e restaura as configurações do Django.
        """
        self.configuracoes.disable()

        self.pasta_midia.cleanup()

        self.pasta_resultados.cleanup()

    @staticmethod
    def _imagem_jpeg(nome="folha.jpg"):
        """
        Gera em memória um arquivo de imagem JPEG válido (32x32) para testes.
        """
        conteudo = BytesIO()

        Image.new("RGB", (32, 32), color=(40, 150, 60)).save(conteudo, format="JPEG")

        return SimpleUploadedFile(nome, conteudo.getvalue(), content_type="image/jpeg")

    def captura_com_umidade(self, umidade, temperatura=25):
        """
        Helper para criar um registro de Captura com leitura ambiental vinculada.
        """
        captura = Captura.objects.create(
            usuario=self.usuario,
            origem=Captura.Origem.MANUAL,
            imagem=self._imagem_jpeg(),
        )

        gerar_leitura_ambiental(captura, temperatura, umidade)

        return captura

    def executor(
        self,
        classe="Tomato___Early_blight",
        confianca=90,
        status="segmentada",
    ):
        """
        Fábrica de mock do executor de análise de IA.
        Simula a criação de artefatos de saída no sistema de arquivos e a estrutura
        de resposta da inferência real (MobileSAM + MobileNetV2).
        """
        def executar(_):
            self.quantidade_execucoes += 1

            id_execucao = f"20261001_120000_{self.quantidade_execucoes:08d}"

            # Cria estrutura física de diretórios simulando a saída da IA
            pasta = Path(self.pasta_resultados.name) / id_execucao / "preprocessamento"

            pasta.mkdir(parents=True)

            imagem_processada = pasta / "imagem_processada.jpg"

            imagem_guia = pasta / "imagem_com_guia.jpg"

            Image.new("RGB", (32, 32), color=(50, 140, 70)).save(imagem_processada)

            Image.new("RGB", (32, 32), color=(80, 120, 90)).save(imagem_guia)

            principais = [
                {"classe": classe, "percentual": confianca},
                {"classe": "Tomato___healthy", "percentual": 7},
                {"classe": "Tomato___Late_blight", "percentual": 3},
            ]

            preprocessamento = SimpleNamespace(
                status=status,
                arquivo_saida=str(imagem_processada),
                arquivo_guia=str(imagem_guia),
                dispositivo="cpu",
                motivos=["baixa_confianca_prevista"] if status == "fallback_roi" else [],
            )

            classificacao = SimpleNamespace(
                classe_prevista=classe,
                confianca_percentual=confianca,
                principais_predicoes=principais,
                tempo_inferencia_ms=120,
            )

            return SimpleNamespace(
                id_execucao=id_execucao,
                preprocessamento=preprocessamento,
                classificacao=classificacao,
                tempo_mobilesam_ms=480.125,
            )

        return executar

    def test_limites_confianca(self):
        """
        Valida se a função `nivel_confianca` categoriza corretamente as faixas:
        - Confiança < 60%: baixa
        - 60% <= Confiança < 80%: media
        - Confiança >= 80%: alta
        """
        self.assertEqual(nivel_confianca("59.99"), "baixa")

        self.assertEqual(nivel_confianca("60"), "media")

        self.assertEqual(nivel_confianca("79.99"), "media")

        self.assertEqual(nivel_confianca("80"), "alta")

    def test_baixa_confianca_tem_prioridade_sobre_alerta_ambiental(self):
        """
        Garante que, em casos de baixa confiança da IA (<60%), o alerta de
        `BAIXA_CONFIANCA` seja gerado prioritariamente, suprimindo o de risco ambiental.
        """
        predicao, criada = processar_captura(
            self.captura_com_umidade(90),
            executor_analise=self.executor(confianca=59),
        )

        self.assertTrue(criada)

        self.assertEqual(
            list(predicao.alertas.values_list("tipo", flat=True)),
            [Alerta.Tipo.BAIXA_CONFIANCA],
        )

    def test_doenca_com_confianca_e_umidade_altas_cria_apenas_alerta_critico(self):
        """
        Garante que a detecção de doença combinada com alta umidade resulta
        exclusivamente na criação de um alerta do tipo `CRITICO`.
        """
        predicao, _ = processar_captura(
            self.captura_com_umidade(85),
            executor_analise=self.executor(classe="Tomato___Late_blight", confianca=80),
        )

        self.assertEqual(
            list(predicao.alertas.values_list("tipo", flat=True)),
            [Alerta.Tipo.CRITICO],
        )

    def test_saudavel_com_umidade_alta_cria_alerta_ambiental(self):
        """
        Garante que a identificação de planta saudável associada a alta umidade
        cria apenas um alerta preventivo do tipo `AMBIENTAL`.
        """
        predicao, _ = processar_captura(
            self.captura_com_umidade(90),
            executor_analise=self.executor(classe="Tomato___healthy", confianca=90),
        )

        self.assertEqual(
            list(predicao.alertas.values_list("tipo", flat=True)),
            [Alerta.Tipo.AMBIENTAL],
        )

    def test_processamento_e_idempotente(self):
        """
        Valida se reprocessar uma mesma captura reusa a predição existente
        sem reexecutar o pipeline de IA (idempotência).
        """
        captura = self.captura_com_umidade(60)

        primeira, primeira_criada = processar_captura(
            captura,
            executor_analise=self.executor(confianca=70),
        )

        segunda, segunda_criada = processar_captura(
            captura,
            executor_analise=self.executor(confianca=90),
        )

        self.assertTrue(primeira_criada)

        self.assertFalse(segunda_criada)

        self.assertEqual(primeira.pk, segunda.pk)

        # Garante que o executor de IA só foi chamado uma única vez
        self.assertEqual(self.quantidade_execucoes, 1)

    def test_fallback_e_tempos_sao_persistidos(self):
        """
        Verifica se métricas de tempo de inferência, status de pré-processamento
        e justificativas de fallback da ROI são salvas corretamente no modelo.
        """
        predicao, _ = processar_captura(
            self.captura_com_umidade(70),
            executor_analise=self.executor(status="fallback_roi"),
        )

        self.assertEqual(predicao.status_preprocessamento, "fallback_roi")

        self.assertEqual(predicao.tempo_inferencia_ms, 120)

        self.assertEqual(predicao.motivos_fallback, ["baixa_confianca_prevista"])

        self.assertTrue(predicao.caminho_imagem_processada.endswith("imagem_processada.jpg"))