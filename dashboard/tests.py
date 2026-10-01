from datetime import timedelta

from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from alerts.models import Alerta
from captures.models import Captura
from predictions.models import Predicao
from sensors.models import LeituraAmbiental

from .services import resumo_painel


class TestesPainel(TestCase):
    """
    Classe de testes unitários e de integração para validação das views,
    regra de negócio e renderização de templates do Dashboard.
    """

    def criar_predicao(self, usuario, classe, confianca, umidade, severidade=None):
        """
        Método auxiliar para criação encadeada de objetos no banco de dados
        (Captura -> Leitura Ambiental -> Predição -> Alerta opcional).
        """

        captura = Captura.objects.create(usuario=usuario, status=Captura.Status.PROCESSADA)

        LeituraAmbiental.objects.create(captura=captura, temperatura=25, umidade=umidade)

        predicao = Predicao.objects.create(
            captura=captura,
            classe_prevista=classe,
            confianca=confianca,
            nivel_confianca=Predicao.NivelConfianca.ALTA,
            tres_principais=[{}, {}, {}],
        )

        if severidade:
            Alerta.objects.create(
                captura=captura,
                predicao=predicao,
                tipo=Alerta.Tipo.AMBIENTAL,
                severidade=severidade,
                mensagem="Alerta de teste",
            )

        return captura, predicao

    def test_templates_nao_possuem_quebras_de_linha_literais(self):
        """
        Garante padronização de arquivos HTML: sem BOM (Byte Order Mark),
        sem caracteres escapados de quebra de linha do Windows (`r`n) e sem linhas em branco no final.
        """

        for arquivo in (settings.BASE_DIR / "templates").rglob("*.html"):
            with self.subTest(arquivo=arquivo.name):
                bytes_do_arquivo = arquivo.read_bytes()

                self.assertFalse(bytes_do_arquivo.startswith(b"\xef\xbb\xbf"))

                conteudo = bytes_do_arquivo.decode("utf-8")

                self.assertNotIn("`r`n", conteudo)

                self.assertFalse(conteudo.endswith("\n\n"))

    def test_inicio_renderiza_apos_login(self):
        """
        Verifica se a página inicial renderiza corretamente após o login
        e contém os elementos de layout básicos (cards, fontes de ícones e navegação).
        """

        usuario = get_user_model().objects.create_user(email="home@example.com", password="test-pass-123")

        self.client.force_login(usuario)

        resposta = self.client.get(reverse("inicio"))

        self.assertEqual(resposta.status_code, 200)

        self.assertContains(resposta, 'class="card-header"', count=4)

        self.assertContains(resposta, 'class="card-header cabecalho-secao"', count=2)

        self.assertContains(resposta, "Monitoramento inteligente")

        self.assertContains(resposta, "font-awesome/6.7.2/css/all.min.css")

        self.assertContains(resposta, 'class="fa-solid fa-house icone-navegacao"')

    def test_barra_administrativa_exibe_icones_font_awesome(self):
        """
        Valida se os ícones do menu de navegação administrativa (staff) são renderizados corretamente.
        """

        usuario = get_user_model().objects.create_user(
            email="icones@example.com",
            password="test-pass-123",
            is_staff=True,
        )

        self.client.force_login(usuario)

        resposta = self.client.get(reverse("inicio"))

        for classe in ("fa-house", "fa-chart-line", "fa-camera", "fa-clock-rotate-left", "fa-bell", "fa-users"):
            with self.subTest(classe=classe):
                self.assertContains(resposta, classe)

    def test_telas_internas_usam_paineis_de_cabecalho_e_conteudo(self):
        """
        Garante que todas as rotas operacionais/internas contêm as estruturas de layout base.
        """

        usuario = get_user_model().objects.create_user(
            email="paineis@example.com",
            password="test-pass-123",
            is_staff=True,
        )

        self.client.force_login(usuario)

        for rota in ("inicio", "painel", "lista_capturas", "criar_captura", "historico", "lista_alertas", "lista_usuarios"):
            with self.subTest(rota=rota):
                resposta = self.client.get(reverse(rota))

                self.assertContains(resposta, "painel-cabecalho")

                self.assertContains(resposta, "painel-conteudo")

    def test_listagens_usam_cartao_interno_para_tabela(self):
        """
        Verifica a presença das classes de tabela responsiva dentro de cards padronizados nas listagens.
        """

        usuario = get_user_model().objects.create_user(
            email="tabelas@example.com",
            password="test-pass-123",
            is_staff=True,
        )

        self.client.force_login(usuario)

        for rota in ("lista_capturas", "historico", "lista_alertas", "lista_usuarios"):
            with self.subTest(rota=rota):
                resposta = self.client.get(reverse(rota))

                self.assertContains(resposta, 'class="cartao-conteudo cartao-conteudo-com-cabecalho"')

                self.assertContains(resposta, 'class="card-header"')

                self.assertContains(resposta, 'class="card-body p-0 table-responsive"')

    def test_painel_renderiza_para_usuario_autenticado(self):
        """
        Métricas e botões básicos do Dashboard para um usuário logado comum.
        """

        usuario = get_user_model().objects.create_user(email="dash@example.com", password="test-pass-123")

        self.client.force_login(usuario)

        resposta = self.client.get(reverse("painel"))

        self.assertEqual(resposta.status_code, 200)

        self.assertContains(resposta, "Dashboard")

        self.assertContains(resposta, 'class="btn btn-success btn-sm"')

    def test_cartoes_com_cabecalho_nao_reintroduzem_espacamento_externo(self):
        """
        Testa a presença de seletores CSS essenciais nos arquivos de estilo da aplicação.
        """

        css_principal = (settings.BASE_DIR / "static/css/app.css").read_text(encoding="utf-8")

        css_responsivo = (settings.BASE_DIR / "static/css/responsivo.css").read_text(encoding="utf-8")

        self.assertIn(".cartao-conteudo.cartao-conteudo-com-cabecalho {", css_principal)

        self.assertIn(".cartao-conteudo.cartao-conteudo-com-cabecalho {", css_responsivo)

        self.assertIn(".cartao-conteudo-com-cabecalho .grafico-vazio", css_principal)

    def test_paginas_operacionais_renderizam_para_administrador(self):
        """
        Confirma se todas as rotas operacionais retornam HTTP 200 para um usuário administrador.
        """

        usuario = get_user_model().objects.create_user(email="staff@example.com", password="test-pass-123", is_staff=True)

        self.client.force_login(usuario)

        for rota in ("inicio", "painel", "lista_capturas", "criar_captura", "historico", "lista_alertas", "lista_usuarios"):
            with self.subTest(rota=rota):
                self.assertEqual(self.client.get(reverse(rota)).status_code, 200)

    def test_painel_vazio_exibe_mensagens_no_lugar_dos_graficos(self):
        """
        Garante que mensagens de estado vazio (empty states) são exibidas quando não há dados cadastrados.
        """

        usuario = get_user_model().objects.create_user(email="vazio@example.com", password="test-pass-123")

        self.client.force_login(usuario)

        resposta = self.client.get(reverse("painel"))

        self.assertContains(resposta, "Ainda não há análises para exibir")

        self.assertContains(resposta, "Ainda não há leituras ambientais")

    def test_painel_administrativo_usa_filtro_em_largura_completa(self):
        """
        Valida os componentes do formulário de filtro exclusivo da visão administrativa.
        """

        usuario = get_user_model().objects.create_user(
            email="filtro-dashboard@example.com",
            password="test-pass-123",
            is_staff=True,
        )

        self.client.force_login(usuario)

        resposta = self.client.get(reverse("painel"))

        self.assertContains(resposta, 'class="campos-filtro"')

        self.assertContains(resposta, 'class="acoes-filtro"')

        self.assertContains(resposta, 'class="btn btn-dark btn-lg"')

        self.assertContains(resposta, ">Filtrar</button>")

    def test_estatisticas_de_classe_calculam_media_e_top_cinco(self):
        """
        Testa o cálculo matemático do serviço `resumo_painel`: média de confiança e ranking de classes.
        """

        usuario = get_user_model().objects.create_user(email="classes@example.com", password="test-pass-123")

        self.criar_predicao(usuario, "Tomato___healthy", 80, 50)

        self.criar_predicao(usuario, "Tomato___healthy", 90, 55)

        self.criar_predicao(usuario, "Tomato___Late_blight", 70, 75)

        contexto = resumo_painel(usuario)

        saudavel = next(item for item in contexto["estatisticas_classes"] if item["classe_prevista"] == "Tomato___healthy")

        self.assertEqual(saudavel["total"], 2)

        self.assertEqual(saudavel["confianca_media"], 85.0)

        self.assertEqual(contexto["principais_classes"][0]["classe_prevista"], "Tomato___healthy")

    def test_alertas_temporais_tem_trinta_dias_e_zeros(self):
        """
        Garante que o histórico temporal de alertas gera um intervalo fixo de 30 dias,
        preenchendo com zero os dias sem registro.
        """

        usuario = get_user_model().objects.create_user(email="alertas-tempo@example.com", password="test-pass-123")

        _, predicao = self.criar_predicao(usuario, "Tomato___Late_blight", 90, 85, Alerta.Severidade.CRITICA)

        alerta = predicao.alertas.get()

        Alerta.objects.filter(pk=alerta.pk).update(criado_em=timezone.now() - timedelta(days=2))

        contexto = resumo_painel(usuario)

        self.assertEqual(len(contexto["linha_tempo_alertas"]), 30)

        self.assertEqual(sum(item["critica"] for item in contexto["linha_tempo_alertas"]), 1)

        self.assertTrue(any(item["critica"] == 0 for item in contexto["linha_tempo_alertas"]))

    def test_novos_dados_respeitam_isolamento_do_usuario(self):
        """
        Valida a regra de isolamento multi-tenant: os dados de um usuário não podem vazar no resumo de outro.
        """

        usuario = get_user_model().objects.create_user(email="isolado@example.com", password="test-pass-123")

        outro = get_user_model().objects.create_user(email="outro-dashboard@example.com", password="test-pass-123")

        self.criar_predicao(usuario, "Tomato___healthy", 88, 50)

        self.criar_predicao(outro, "Tomato___Late_blight", 99, 90, Alerta.Severidade.CRITICA)

        contexto = resumo_painel(usuario)

        self.assertEqual(len(contexto["estatisticas_classes"]), 1)

        self.assertEqual(contexto["estatisticas_classes"][0]["classe_prevista"], "Tomato___healthy")

        self.assertFalse(contexto["linha_tempo_alertas_possui_dados"])

    def test_painel_renderiza_novos_componentes_e_estados_vazios(self):
        """
        Verifica se os componentes específicos e o script JS dos gráficos do Dashboard estão na resposta da requisição.
        """

        usuario = get_user_model().objects.create_user(email="graficos-vazios@example.com", password="test-pass-123")

        self.client.force_login(usuario)

        resposta = self.client.get(reverse("painel"))

        self.assertContains(resposta, "Confiança média por classe")

        self.assertContains(resposta, "Alertas por severidade")

        self.assertNotContains(resposta, "Umidade × doenças e alertas")

        self.assertContains(resposta, "5 classes mais detectadas")

        self.assertContains(resposta, "js/dashboard-graficos.js")
