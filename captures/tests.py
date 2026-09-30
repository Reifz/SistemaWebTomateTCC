from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import Capture


class CaptureViewTests(TestCase):
    """
    Suíte de testes para validar o fluxo de views do app de Captures, incluindo:
    - Controle de acesso de usuários anônimos (redirecionamento de login).
    - Criação de capturas e integração automática com leituras ambientais.
    - Isolamento multitenant/permissões entre usuários.
    - Validação de renderização de componentes e classes CSS no template.
    """

    def setUp(self):
        """Prepara dois usuários distintos para testes de permissão e isolamento de dados."""
        self.user = get_user_model().objects.create_user(
            email="web@example.com", 
            password="test-pass-123"
        )
        self.other = get_user_model().objects.create_user(
            email="other@example.com", 
            password="test-pass-123"
        )

    def test_views_redirect_anonymous_user(self):
        """
        Garante a proteção da view por autenticação:
        usuários não autenticados devem ser redirecionados para a tela de login.
        """
        response = self.client.get(reverse("capture_list"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('capture_list')}")

    def test_create_capture_generates_environmental_reading(self):
        """
        Valida se o formulário de criação salva a captura no banco de dados e gera 
        automaticamente o registro de leitura ambiental (temperatura e umidade) associado.
        """
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("capture_create"), 
            {
                "origin": "simulado", 
                "observation": "Teste", 
                "temperature": "24.50", 
                "humidity": "70.00"
            }
        )
        capture = Capture.objects.get(user=self.user)
        
        # Redireciona para os detalhes da captura após o cadastro com sucesso
        self.assertRedirects(response, reverse("capture_detail", args=[capture.pk]))
        # Verifica se o valor numérico da umidade foi salvo corretamente
        self.assertEqual(capture.environmental_reading.humidity, 70)

    def test_capture_detail_is_isolated_by_user(self):
        """
        Testa a política de segurança de isolamento de dados:
        um usuário comum não deve conseguir acessar o detalhe da captura pertencente a outro usuário (retorna 404).
        """
        capture = Capture.objects.create(user=self.other)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("capture_detail", args=[capture.pk])).status_code, 404)

    def test_detalhe_usa_paineis_de_cabecalho_e_conteudo(self):
        """
        Verifica se a página de detalhes renderiza a estrutura de layout e os elementos
        esperados no HTML (painéis de cabeçalho, botões e cartões de conteúdo).
        """
        captura = Capture.objects.create(user=self.user)
        self.client.force_login(self.user)

        resposta = self.client.get(reverse("capture_detail", args=[captura.pk]))

        # Presença das divisões e painéis estruturais do template
        self.assertContains(resposta, "painel-cabecalho")
        self.assertContains(resposta, "painel-conteudo")
        
        # Estilização de botões e contagem de cards de conteúdo (esperado exatamente 3 cards)
        self.assertContains(resposta, 'class="btn btn-light"')
        self.assertContains(resposta, 'class="content-card capture-card', count=3)
        self.assertContains(resposta, 'class="capture-card-header"', count=3)
        
        # Textos informativos padrão dentro dos cartões
        self.assertContains(resposta, "Dados da captura")
        self.assertContains(resposta, "Não informada")

    def test_filtros_usam_layout_flexivel_e_botao_em_largura_completa(self):
        """
        Testa a renderização do formulário de filtros na página de listagem para usuários da equipe (staff),
        garantindo o uso das classes CSS corretas para layout responsivo/flexível.
        """
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        Capture.objects.create(user=self.user)
        self.client.force_login(self.user)
        
        resposta = self.client.get(reverse("capture_list"))
        
        # Presença do grid/flexbox e das ações de filtro
        self.assertContains(resposta, 'class="filter-fields"')
        self.assertContains(resposta, 'class="filter-field filter-field-search"')
        self.assertContains(resposta, 'class="filter-actions"')
        self.assertContains(resposta, 'class="btn btn-dark btn-lg"')
        
        # Garante que botões e links específicos estejam presentes/ausentes conforme especificação do design
        self.assertNotContains(resposta, ">Limpar</a>")
        self.assertContains(resposta, 'class="btn btn-success btn-sm"')