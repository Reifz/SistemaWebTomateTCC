import ast
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

# Mapeamento de arquivos Python sujeitos às regras de formatação e espaçamento vertical
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

# Mapeamento de arquivos JavaScript sujeitos às regras de formatação
ARQUIVOS_LOGICA_JAVASCRIPT = (
    "static/js/dashboard-graficos.js",
)


class TesteEstiloCodigo(SimpleTestCase):
    """
    Suíte de testes de linting e validação de estilo de código (estilização vertical).
    Garante que declarações e instruções contíguas no código possuam linhas em branco de separação,
    forçando legibilidade e um padrão estético uniforme no projeto.
    """

    def test_instrucoes_python_possuem_linha_em_branco_entre_si(self):
        """
        Analisa a Árvore de Sintaxe Abstrata (AST) dos arquivos Python e valida se existe
        ao menos uma linha em branco entre instruções consecutivas no mesmo bloco
        (com exceção de blocos contínuos de imports).
        """
        ocorrencias = []

        for caminho_relativo in ARQUIVOS_LOGICA_PYTHON:
            caminho = settings.BASE_DIR / caminho_relativo

            conteudo = caminho.read_text(encoding="utf-8")

            linhas = conteudo.splitlines()

            # Constrói a AST para análise estrutural exata das instruções
            arvore = ast.parse(conteudo, filename=str(caminho))

            for instrucoes in self._listas_de_instrucoes(arvore):
                for anterior, atual in zip(instrucoes, instrucoes[1:]):
                    # Permite imports consecutivos sem exigir linha em branco entre eles
                    if isinstance(anterior, (ast.Import, ast.ImportFrom)) and isinstance(atual, (ast.Import, ast.ImportFrom)):
                        continue

                    fim_anterior = anterior.end_lineno

                    inicio_atual = self._inicio_unidade(atual)

                    # Recua a linha inicial se a instrução atual possuir comentários imediatamente acima
                    while inicio_atual > fim_anterior + 1 and linhas[inicio_atual - 2].strip().startswith("#"):
                        inicio_atual -= 1

                    intervalo = linhas[fim_anterior:inicio_atual - 1]

                    # Valida se há pelo menos uma linha vazia no intervalo
                    if not any(not linha.strip() for linha in intervalo):
                        ocorrencias.append(f"{caminho_relativo}:{fim_anterior}")

        self.assertEqual(
            [],
            ocorrencias,
            "Instruções Python sem uma linha em branco entre si:\n" + "\n".join(ocorrencias),
        )

    def test_instrucoes_javascript_possuem_linha_em_branco_entre_si(self):
        """
        Analisa o código JavaScript linha a linha para verificar a presença de linhas
        em branco entre declarações finalizadas com ponto e vírgula `;`.
        """
        ocorrencias = []

        for caminho_relativo in ARQUIVOS_LOGICA_JAVASCRIPT:
            caminho = settings.BASE_DIR / caminho_relativo

            linhas = caminho.read_text(encoding="utf-8").splitlines()

            for indice, linha in enumerate(linhas[:-1]):
                atual = linha.strip()

                proxima = linhas[indice + 1].strip()

                # Ignora linhas que não terminam instrução ou se a próxima já for vazia
                if not atual.endswith(";") or not proxima:
                    continue

                # Ignora fechamento de blocos ou continuações sintáticas (else, catch, etc.)
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
        """
        Calcula o número da linha inicial real de um nó da AST, levando em consideração
        decorators caso o nó seja uma função ou classe.
        """
        linhas = [no.lineno]

        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            linhas.extend(decorador.lineno for decorador in no.decorator_list)

        return min(linhas)

    @classmethod
    def _listas_de_instrucoes(cls, no):
        """
        Navega recursivamente pelos campos da AST para identificar e produzir listas
        de instruções (ast.stmt) contidas no mesmo escopo/bloco.
        """
        for _, valor in ast.iter_fields(no):
            if isinstance(valor, list) and valor and all(isinstance(item, ast.stmt) for item in valor):
                yield valor

            if isinstance(valor, ast.AST):
                yield from cls._listas_de_instrucoes(valor)

            elif isinstance(valor, list):
                for item in valor:
                    if isinstance(item, ast.AST):
                        yield from cls._listas_de_instrucoes(item)