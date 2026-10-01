import ast
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


IDENTIFICADORES_ANTIGOS = {
    "Account",
    "Alert",
    "AlertsConfig",
    "PredictorSAM",
    "Capture",
    "CapturesConfig",
    "DashboardConfig",
    "EnvironmentalReading",
    "FixedRandom",
    "Prediction",
    "PredictionsConfig",
    "SensorsConfig",
    "account",
    "alert",
    "array",
    "capture",
    "captures",
    "created",
    "device",
    "environmental_reading",
    "first_created",
    "imagem_path",
    "logger",
    "mascara_full",
    "mark_read",
    "member",
    "other",
    "parser",
    "prediction",
    "predictions",
    "predictor",
    "q",
    "response",
    "second_created",
    "user_list",
    "user_create",
    "user_edit",
    "capture_list",
    "capture_create",
    "capture_detail",
    "capture_process",
    "alert_list",
}

# Estes atributos materializam contratos JSON públicos e, por isso, não podem
# ser traduzidos sem quebrar o ESP32 e outros consumidores da API.
EXCECOES_CONTRATOS_EXTERNOS = {
    (Path("api/serializers.py"), "environmental_reading"),
}

MARCADORES_FRONTEND_ANTIGOS = {
    "AgroMonitor",
    "Tomato Monitor",
    "content-card",
    "capture-card",
    "filter-panel",
    "filter-fields",
    "filter-field",
    "filter-actions",
    "metric-card",
    "page-heading",
    "section-heading",
    "status-pill",
    "empty-state",
    "alert-row",
    "severity-dot",
    "chart-container",
    "chart-empty",
    "page_obj",
    "querystring",
    "latest_captures",
    "latest_alerts",
    "total_captures",
    "processed_captures",
    "active_alerts",
    "diseases_detected",
}


class TesteNomenclaturaPortugues(SimpleTestCase):
    def test_codigo_python_nao_reintroduz_identificadores_antigos(self):
        ocorrencias = []

        for caminho in self._arquivos_python():
            arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))

            for no in ast.walk(arvore):
                nome = self._nome_definido(no)

                caminho_relativo = caminho.relative_to(settings.BASE_DIR)

                if nome in IDENTIFICADORES_ANTIGOS and (caminho_relativo, nome) not in EXCECOES_CONTRATOS_EXTERNOS:
                    ocorrencias.append(f"{caminho.relative_to(settings.BASE_DIR)}:{no.lineno}:{nome}")

        self.assertEqual([], ocorrencias, "Identificadores próprios em inglês encontrados:\n" + "\n".join(ocorrencias))

    def test_frontend_nao_reintroduz_nomenclatura_antiga(self):
        ocorrencias = []

        for caminho in self._arquivos_frontend():
            conteudo = caminho.read_text(encoding="utf-8")

            for marcador in MARCADORES_FRONTEND_ANTIGOS:
                if marcador in conteudo:
                    ocorrencias.append(f"{caminho.relative_to(settings.BASE_DIR)}:{marcador}")

        self.assertEqual([], ocorrencias, "Nomenclatura antiga encontrada no frontend:\n" + "\n".join(ocorrencias))

    @staticmethod
    def _nome_definido(no):
        if isinstance(no, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            return no.name

        if isinstance(no, ast.Name) and isinstance(no.ctx, ast.Store):
            return no.id

        if isinstance(no, ast.arg):
            return no.arg

        return None

    @staticmethod
    def _arquivos_python():
        pastas = ("accounts", "alerts", "api", "captures", "dashboard", "predictions", "sensors", "agromonitor")

        for pasta in pastas:
            for caminho in (settings.BASE_DIR / pasta).rglob("*.py"):
                if "migrations" not in caminho.parts and caminho.name != "test_nomenclatura.py":
                    yield caminho

    @staticmethod
    def _arquivos_frontend():
        yield settings.BASE_DIR / "README.md"

        for pasta, extensoes in (("templates", ("*.html",)), ("static", ("*.css", "*.js"))):
            for extensao in extensoes:
                yield from (settings.BASE_DIR / pasta).rglob(extensao)
