import ast
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


ARQUIVOS_LOGICA_PYTHON = (
    "accounts/admin.py",
    "accounts/context_processors.py",
    "accounts/forms.py",
    "accounts/models.py",
    "accounts/tests.py",
    "accounts/views.py",
    "alerts/admin.py",
    "alerts/context_processors.py",
    "alerts/models.py",
    "alerts/services.py",
    "alerts/views.py",
    "api/serializers.py",
    "api/tests.py",
    "api/views.py",
    "captures/admin.py",
    "captures/forms.py",
    "captures/management/commands/seed_demo.py",
    "captures/models.py",
    "captures/services.py",
    "captures/tests.py",
    "captures/views.py",
    "dashboard/services.py",
    "dashboard/test_estilo_codigo.py",
    "dashboard/test_nomenclatura.py",
    "dashboard/tests.py",
    "dashboard/views.py",
    "predictions/admin.py",
    "predictions/inferencia/__init__.py",
    "predictions/inferencia/classificador.py",
    "predictions/inferencia/pipeline.py",
    "predictions/inferencia/preprocessamento.py",
    "predictions/inferencia/preprocessamento_io.py",
    "predictions/management/commands/limpar_resultados_ia.py",
    "predictions/management/commands/validar_ia_real.py",
    "predictions/models.py",
    "predictions/services.py",
    "predictions/tests.py",
    "predictions/views.py",
    "sensors/admin.py",
    "sensors/models.py",
)

ARQUIVOS_LOGICA_JAVASCRIPT = (
    "static/js/dashboard-graficos.js",
)


class TesteEstiloCodigo(SimpleTestCase):
    def test_instrucoes_python_possuem_linha_em_branco_entre_si(self):
        ocorrencias = []

        for caminho_relativo in ARQUIVOS_LOGICA_PYTHON:
            caminho = settings.BASE_DIR / caminho_relativo

            conteudo = caminho.read_text(encoding="utf-8")

            linhas = conteudo.splitlines()

            arvore = ast.parse(conteudo, filename=str(caminho))

            for instrucoes in self._listas_de_instrucoes(arvore):
                for anterior, atual in zip(instrucoes, instrucoes[1:]):
                    if isinstance(anterior, (ast.Import, ast.ImportFrom)) and isinstance(atual, (ast.Import, ast.ImportFrom)):
                        continue

                    fim_anterior = anterior.end_lineno

                    inicio_atual = self._inicio_unidade(atual)

                    while inicio_atual > fim_anterior + 1 and linhas[inicio_atual - 2].strip().startswith("#"):
                        inicio_atual -= 1

                    intervalo = linhas[fim_anterior:inicio_atual - 1]

                    if not any(not linha.strip() for linha in intervalo):
                        ocorrencias.append(f"{caminho_relativo}:{fim_anterior}")

        self.assertEqual(
            [],
            ocorrencias,
            "Instruções Python sem uma linha em branco entre si:\n" + "\n".join(ocorrencias),
        )

    def test_instrucoes_javascript_possuem_linha_em_branco_entre_si(self):
        ocorrencias = []

        for caminho_relativo in ARQUIVOS_LOGICA_JAVASCRIPT:
            caminho = settings.BASE_DIR / caminho_relativo

            linhas = caminho.read_text(encoding="utf-8").splitlines()

            for indice, linha in enumerate(linhas[:-1]):
                atual = linha.strip()

                proxima = linhas[indice + 1].strip()

                if not atual.endswith(";") or not proxima:
                    continue

                if proxima.startswith(("}", "]", ")", "else", "catch", "finally")):
                    continue

                ocorrencias.append(f"{caminho_relativo}:{indice + 1}")

        self.assertEqual(
            [],
            ocorrencias,
            "Instruções JavaScript sem uma linha em branco entre si:\n" + "\n".join(ocorrencias),
        )

    @staticmethod
    def _inicio_unidade(no):
        linhas = [no.lineno]

        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            linhas.extend(decorador.lineno for decorador in no.decorator_list)

        return min(linhas)

    @classmethod
    def _listas_de_instrucoes(cls, no):
        for _, valor in ast.iter_fields(no):
            if isinstance(valor, list) and valor and all(isinstance(item, ast.stmt) for item in valor):
                yield valor

            if isinstance(valor, ast.AST):
                yield from cls._listas_de_instrucoes(valor)

            elif isinstance(valor, list):
                for item in valor:
                    if isinstance(item, ast.AST):
                        yield from cls._listas_de_instrucoes(item)
