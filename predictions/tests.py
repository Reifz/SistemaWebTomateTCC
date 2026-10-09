import ast
import inspect
import tempfile
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from alerts.models import Alerta
from captures.models import Captura
from predictions.inferencia import pipeline as pipeline_inferencia
from predictions.inferencia import preprocessamento_principal
from predictions.inferencia.preprocessamento import GeometriaGuia
from predictions.services import gerar_leitura_ambiental, nivel_confianca, processar_captura


class PreditorQuatroCentros:
    def set_image(self, imagem):
        self.imagem = imagem

    def predict(self, **argumentos):
        mascara = np.zeros((200, 200), np.uint8)

        for centro in ((65, 65), (135, 65), (65, 135), (135, 135)):
            cv2.circle(mascara, centro, 25, 1, -1)

        cv2.line(mascara, (65, 65), (135, 65), 1, 3)

        cv2.line(mascara, (65, 135), (135, 135), 1, 3)

        cv2.line(mascara, (65, 65), (65, 135), 1, 3)

        cv2.line(mascara, (135, 65), (135, 135), 1, 3)

        cv2.line(mascara, (65, 65), (135, 135), 1, 3)

        if argumentos.get("multimask_output", False):
            mascaras = np.asarray([mascara, mascara, mascara], dtype=bool)

            pontuacoes = np.asarray([0.95, 0.90, 0.85], np.float32)

            logitos = np.ones((3, 256, 256), np.float32)

            return mascaras, pontuacoes, logitos

        return (
            np.asarray([mascara], dtype=bool),
            np.asarray([0.94], np.float32),
            np.ones((1, 256, 256), np.float32),
        )


class TestesPreprocessamentoPrincipal(SimpleTestCase):
    @staticmethod
    def _importacoes(modulo):
        arvore = ast.parse(inspect.getsource(modulo))

        return [
            no.module or ""
            for no in ast.walk(arvore)
            if isinstance(no, ast.ImportFrom)
        ] + [
            apelido.name
            for no in ast.walk(arvore)
            if isinstance(no, ast.Import)
            for apelido in no.names
        ]

    def test_producao_nao_importa_versoes_experimentais(self):
        for modulo in (preprocessamento_principal, pipeline_inferencia):
            self.assertFalse(
                any(
                    nome.startswith("mobilesam_versions")
                    for nome in self._importacoes(modulo)
                )
            )

    def test_entrada_do_classificador_permanece_em_224(self):
        visual = np.full((413, 287, 3), 120, np.uint8)

        imagem_modelo = preprocessamento_principal.gerar_imagem_modelo(visual)

        self.assertEqual((224, 224, 3), imagem_modelo.shape)

    def test_avisos_de_qualidade_nao_bloqueiam_a_captura(self):
        imagem = np.full((200, 300, 3), 120, np.uint8)

        qualidade = preprocessamento_principal.avaliar_qualidade_captura(
            imagem,
            "esquerda",
        )

        self.assertEqual("atencao", qualidade.status)

        self.assertIn("baixa_nitidez", qualidade.avisos)

        self.assertIn("baixa_resolucao", qualidade.avisos)

        self.assertIn("folha_fora_do_centro", qualidade.avisos)

    def test_bloqueia_separacao_com_mais_de_tres_centros(self):
        preditor = preprocessamento_principal.PreditorPrincipal(
            PreditorQuatroCentros()
        )

        mascaras, _, _ = preditor.predict(
            point_coords=np.asarray([[100, 100]], np.float32),
            point_labels=np.asarray([1], np.int32),
            box=np.asarray([20, 20, 180, 180], np.float32),
            multimask_output=True,
        )

        self.assertEqual(3, len(mascaras))

        self.assertEqual(4, preditor.metricas_lobos["centros_detectados"])

        self.assertEqual(
            "complexidade_maior_que_tres_centros",
            preditor.metricas_lobos["separacao_bloqueada"],
        )

    def test_limpeza_preserva_componente_do_prompt(self):
        mascara = np.zeros((100, 100), dtype=bool)

        mascara[20:80, 20:80] = True

        mascara[2:5, 2:5] = True

        guia = GeometriaGuia(0, 0, 100, 50, 50)

        mascara_limpa, metricas = preprocessamento_principal.limpar_mascara(
            mascara,
            guia,
        )

        self.assertTrue(mascara_limpa[50, 50])

        self.assertFalse(mascara_limpa[3, 3])

        self.assertTrue(metricas["limpeza_aplicada"])


class TestesServicoPredicao(TestCase):
    def setUp(self):
        self.pasta_midia = tempfile.TemporaryDirectory()

        self.pasta_resultados = tempfile.TemporaryDirectory()

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
        self.configuracoes.disable()

        self.pasta_midia.cleanup()

        self.pasta_resultados.cleanup()

    @staticmethod
    def _imagem_jpeg(nome="folha.jpg"):
        conteudo = BytesIO()

        Image.new("RGB", (32, 32), color=(40, 150, 60)).save(conteudo, format="JPEG")

        return SimpleUploadedFile(nome, conteudo.getvalue(), content_type="image/jpeg")

    def captura_com_umidade(self, umidade, temperatura=25):
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
        def executar(_):
            self.quantidade_execucoes += 1

            id_execucao = f"20261001_120000_{self.quantidade_execucoes:08d}"

            pasta = Path(self.pasta_resultados.name) / id_execucao / "preprocessamento"

            pasta.mkdir(parents=True)

            imagem_visual = pasta / "imagem_processada_visual.png"

            imagem_modelo = pasta / "imagem_modelo.png"

            imagem_guia = pasta / "imagem_com_guia.jpg"

            Image.new("RGB", (32, 32), color=(50, 140, 70)).save(imagem_visual)

            Image.new("RGB", (224, 224), color=(50, 140, 70)).save(imagem_modelo)

            Image.new("RGB", (32, 32), color=(80, 120, 90)).save(imagem_guia)

            principais = [
                {"classe": classe, "percentual": confianca},
                {"classe": "Tomato___healthy", "percentual": 7},
                {"classe": "Tomato___Late_blight", "percentual": 3},
            ]

            preprocessamento = SimpleNamespace(
                status=status,
                arquivo_saida=str(imagem_modelo),
                arquivo_visual=str(imagem_visual),
                arquivo_modelo=str(imagem_modelo),
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
        self.assertEqual(nivel_confianca("59.99"), "baixa")

        self.assertEqual(nivel_confianca("60"), "media")

        self.assertEqual(nivel_confianca("79.99"), "media")

        self.assertEqual(nivel_confianca("80"), "alta")

    def test_baixa_confianca_tem_prioridade_sobre_alerta_ambiental(self):
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
        predicao, _ = processar_captura(
            self.captura_com_umidade(85),
            executor_analise=self.executor(classe="Tomato___Late_blight", confianca=80),
        )

        self.assertEqual(
            list(predicao.alertas.values_list("tipo", flat=True)),
            [Alerta.Tipo.CRITICO],
        )

    def test_saudavel_com_umidade_alta_cria_alerta_ambiental(self):
        predicao, _ = processar_captura(
            self.captura_com_umidade(90),
            executor_analise=self.executor(classe="Tomato___healthy", confianca=90),
        )

        self.assertEqual(
            list(predicao.alertas.values_list("tipo", flat=True)),
            [Alerta.Tipo.AMBIENTAL],
        )

    def test_processamento_e_idempotente(self):
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

        self.assertEqual(self.quantidade_execucoes, 1)

    def test_fallback_e_tempos_sao_persistidos(self):
        predicao, _ = processar_captura(
            self.captura_com_umidade(70),
            executor_analise=self.executor(status="fallback_roi"),
        )

        self.assertEqual(predicao.status_preprocessamento, "fallback_roi")

        self.assertEqual(predicao.tempo_inferencia_ms, 120)

        self.assertEqual(predicao.motivos_fallback, ["baixa_confianca_prevista"])

        self.assertTrue(
            predicao.caminho_imagem_processada.endswith(
                "imagem_processada_visual.png"
            )
        )
