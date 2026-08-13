import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse

from captures.models import Capture


User = get_user_model()


class UserManagementTests(TestCase):
    def setUp(self):
        self.pasta_midia = tempfile.mkdtemp()
        self.configuracao_midia = override_settings(MEDIA_ROOT=self.pasta_midia)
        self.configuracao_midia.enable()
        self.admin = User.objects.create_user(email="admin@example.com", password="strong-pass-123", is_staff=True)
        self.member = User.objects.create_user(email="member@example.com", password="strong-pass-123")

    def tearDown(self):
        self.configuracao_midia.disable()
        shutil.rmtree(self.pasta_midia, ignore_errors=True)
        super().tearDown()

    def test_regular_user_cannot_open_user_management(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(reverse("user_list")).status_code, 302)

    def test_admin_can_create_user(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("user_create"), {
            "first_name": "Maria", "last_name": "Silva", "email": "maria@example.com",
            "password1": "safe-password-987", "password2": "safe-password-987",
            "is_active": "on",
        })
        self.assertRedirects(response, reverse("user_list"))
        self.assertTrue(User.objects.get(email="maria@example.com").check_password("safe-password-987"))

    def test_admin_cannot_disable_self(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("user_edit", args=[self.admin.pk]), {
            "email": self.admin.email, "is_staff": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "não pode desativar")
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_dropdown_exibe_acoes_administrativas_somente_para_staff(self):
        self.client.force_login(self.admin)
        resposta_admin = self.client.get(reverse("home"))
        self.assertContains(resposta_admin, "Inserir Dados")
        self.assertContains(resposta_admin, "Truncar Dados")
        self.assertContains(resposta_admin, "Perfil")

        self.client.force_login(self.member)
        resposta_membro = self.client.get(reverse("home"))
        self.assertNotContains(resposta_membro, "Inserir Dados")
        self.assertNotContains(resposta_membro, "Truncar Dados")
        self.assertContains(resposta_membro, "Perfil")

    def test_perfil_atualiza_senha_e_mantem_sessao(self):
        self.client.force_login(self.member)
        resposta = self.client.post(reverse("perfil"), {
            "first_name": "João",
            "last_name": "Silva",
            "email": self.member.email,
            "nova_senha": "nova-senha-segura-987",
            "confirmar_senha": "nova-senha-segura-987",
        })
        self.assertRedirects(resposta, reverse("perfil"))
        self.member.refresh_from_db()
        self.assertEqual(self.member.first_name, "João")
        self.assertTrue(self.member.check_password("nova-senha-segura-987"))
        self.assertEqual(self.client.get(reverse("perfil")).status_code, 200)

    def test_usuario_comum_nao_pode_gerenciar_dados(self):
        captura = Capture.objects.create(user=self.member)
        self.client.force_login(self.member)
        self.assertEqual(self.client.post(reverse("truncar_dados")).status_code, 302)
        self.assertEqual(self.client.post(reverse("inserir_dados")).status_code, 302)
        self.assertTrue(Capture.objects.filter(pk=captura.pk).exists())

    def test_acoes_de_dados_rejeitam_get(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("truncar_dados")).status_code, 405)
        self.assertEqual(self.client.get(reverse("inserir_dados")).status_code, 405)

    def test_admin_insere_dados_para_todos_os_usuarios_ativos(self):
        self.client.force_login(self.admin)
        resposta = self.client.post(reverse("inserir_dados"))
        self.assertRedirects(resposta, reverse("home"))
        self.assertEqual(Capture.objects.filter(user=self.admin, origin=Capture.Origin.SIMULATED).count(), 12)
        self.assertEqual(Capture.objects.filter(user=self.member, origin=Capture.Origin.SIMULATED).count(), 12)
        self.assertEqual(Capture.objects.exclude(image="").count(), 24)

    def test_admin_trunca_dados_mas_preserva_usuarios(self):
        captura = Capture.objects.create(user=self.member)
        captura.image.save("teste.jpg", ContentFile(b"imagem"), save=True)
        caminho = captura.image.path
        self.client.force_login(self.admin)

        with self.captureOnCommitCallbacks(execute=True):
            resposta = self.client.post(reverse("truncar_dados"))

        self.assertRedirects(resposta, reverse("home"))
        self.assertEqual(Capture.objects.count(), 0)
        self.assertEqual(User.objects.count(), 2)
        self.assertFalse(__import__("pathlib").Path(caminho).exists())
