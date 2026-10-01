from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import Captura


class TestesVisoesCaptura(TestCase):
    """
    Suíte de testes para validar o fluxo de views do app de Captures, incluindo:
    - Controle de acesso de usuários anônimos (redirecionamento de login).
    - Criação de capturas e integração automática com leituras ambientais.
    - Isolamento multitenant/permissões entre usuários.
    - Validação de renderização de componentes e classes CSS no template.
    """

    def setUp(self):
        """Prepara dois usuários distintos para testes de permissão e isolamento de dados."""

        self.usuario = get_user_model().objects.create_user(
            email="web@example.com",
            password="test-pass-123"
        )

        self.outro_usuario = get_user_model().objects.create_user(
            email="other@example.com",
            password="test-pass-123"
        )

    def test_visoes_redirecionam_usuario_anonimo(self):
        """
        Garante a proteção da view por autenticação:
        usuários não autenticados devem ser redirecionados para a tela de login.
        """

        resposta = self.client.get(reverse("lista_capturas"))

        self.assertRedirects(resposta, f"{reverse('login')}?next={reverse('lista_capturas')}")

    def test_criar_captura_gera_leitura_ambiental(self):
        """
        Valida se o formulário de criação salva a captura no banco de dados e gera
        automaticamente o registro de leitura ambiental (temperatura e umidade) associado.
        """

        self.client.force_login(self.usuario)

        resposta = self.client.post(
            reverse("criar_captura"),
            {
                "origem": "simulado",
                "observacao": "Teste",
                "temperatura": "24.50",
                "umidade": "70.00",
            }
        )

        captura = Captura.objects.get(usuario=self.usuario)

        # Redireciona para os detalhes da captura após o cadastro com sucesso
        self.assertRedirects(resposta, reverse("detalhar_captura", args=[captura.pk]))

        # Verifica se o valor numérico da umidade foi salvo corretamente
        self.assertEqual(captura.leitura_ambiental.umidade, 70)

    def test_detalhe_captura_e_isolado_por_usuario(self):
        """
        Testa a política de segurança de isolamento de dados:
        um usuário comum não deve conseguir acessar o detalhe da captura pertencente a outro usuário (retorna 404).
        """

        captura = Captura.objects.create(usuario=self.outro_usuario)

        self.client.force_login(self.usuario)

        self.assertEqual(self.client.get(reverse("detalhar_captura", args=[captura.pk])).status_code, 404)

    def test_detalhe_usa_paineis_de_cabecalho_e_conteudo(self):
        """
        Verifica se a página de detalhes renderiza a estrutura de layout e os elementos
        esperados no HTML (painéis de cabeçalho, botões e cartões de conteúdo).
        """

        captura = Captura.objects.create(usuario=self.usuario)

        self.client.force_login(self.usuario)

        resposta = self.client.get(reverse("detalhar_captura", args=[captura.pk]))

        # Presença das divisões e painéis estruturais do template
        self.assertContains(resposta, "painel-cabecalho")

        self.assertContains(resposta, "painel-conteudo")

        # Estilização de botões e contagem de cards de conteúdo (esperado exatamente 3 cards)
        self.assertContains(resposta, 'class="btn btn-light"')

        self.assertContains(resposta, 'class="cartao-conteudo cartao-captura', count=3)

        self.assertContains(resposta, 'class="cabecalho-cartao-captura"', count=3)

        # Textos informativos padrão dentro dos cartões
        self.assertContains(resposta, "Dados da captura")

        self.assertContains(resposta, "Não informada")

    def test_filtros_usam_layout_flexivel_e_botao_em_largura_completa(self):
        """
        Testa a renderização do formulário de filtros na página de listagem para usuários da equipe (staff),
        garantindo o uso das classes CSS corretas para layout responsivo/flexível.
        """

        self.usuario.is_staff = True

        self.usuario.save(update_fields=["is_staff"])

        Captura.objects.create(usuario=self.usuario)

        self.client.force_login(self.usuario)

        resposta = self.client.get(reverse("lista_capturas"))

        # Presença do grid/flexbox e das ações de filtro
        self.assertContains(resposta, 'class="campos-filtro"')

        self.assertContains(resposta, 'class="campo-filtro campo-filtro-pesquisa"')

        self.assertContains(resposta, 'class="acoes-filtro"')

        self.assertContains(resposta, 'class="btn btn-dark btn-lg"')

        # Garante que botões e links específicos estejam presentes/ausentes conforme especificação do design
        self.assertNotContains(resposta, ">Limpar</a>")

        self.assertContains(resposta, 'class="btn btn-success btn-sm"')
