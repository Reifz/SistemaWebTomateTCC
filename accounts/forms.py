from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

Usuario = get_user_model()


class FormularioEstilizado:
    """
    Mixin auxiliar que percorre os campos do formulário para injetar dinamicamente
    as classes CSS do Bootstrap (`form-control` e `form-check-input`) nos widgets.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for campo in self.fields.values():
            campo.widget.attrs["class"] = (
                "form-check-input" if isinstance(campo.widget, forms.CheckboxInput) else "form-control"
            )


class FormularioCriacaoUsuario(FormularioEstilizado, forms.ModelForm):
    """
    Formulário administrativo para criação de novos usuários, com validação de senha
    em dois campos e criptografia automática no salvamento.
    """
    senha = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput,
        validators=[validate_password]
    )

    confirmacao_senha = forms.CharField(
        label="Confirmar senha",
        widget=forms.PasswordInput
    )

    class Meta:
        model = Usuario
        fields = ("first_name", "last_name", "email", "is_staff", "is_active")
        labels = {
            "first_name": "Nome",
            "last_name": "Sobrenome",
            "is_staff": "Administrador",
            "is_active": "Conta ativa"
        }

    def clean(self):
        """Valida se os campos 'senha' e 'confirmacao_senha' são idênticos."""
        dados = super().clean()

        if dados.get("senha") != dados.get("confirmacao_senha"):
            self.add_error("confirmacao_senha", "As senhas não coincidem.")

        return dados

    def save(self, commit=True):
        """Aplica o algoritmo de hash na senha do usuário antes de persistir no banco."""
        usuario = super().save(commit=False)
        usuario.set_password(self.cleaned_data["senha"])

        if commit:
            usuario.save()

        return usuario


class FormularioEdicaoUsuario(FormularioEstilizado, forms.ModelForm):
    """
    Formulário para edição de usuários por administradores.
    Contém proteção contra auto-desativação e revogação do próprio acesso administrativo.
    """

    nova_senha = forms.CharField(
        label="Nova senha",
        required=False,
        widget=forms.PasswordInput,
        validators=[validate_password],
        help_text="Deixe em branco para manter a senha atual."
    )

    class Meta:
        model = Usuario
        fields = ("first_name", "last_name", "email", "is_staff", "is_active")
        labels = {
            "first_name": "Nome",
            "last_name": "Sobrenome",
            "is_staff": "Administrador",
            "is_active": "Conta ativa"
        }

    def __init__(self, *args, usuario_logado=None, **kwargs):
        # Armazena o usuário atualmente autenticado para validar permissões de auto-edição
        self.usuario_logado = usuario_logado
        super().__init__(*args, **kwargs)

    def clean(self):
        """Impede que o administrador logado desative a si próprio ou remova seu acesso admin."""
        dados = super().clean()

        if self.instance == self.usuario_logado:
            if not dados.get("is_active"):
                self.add_error("is_active", "Você não pode desativar a própria conta.")

            if not dados.get("is_staff"):
                self.add_error("is_staff", "Você não pode remover seu próprio acesso administrativo.")

        return dados

    def save(self, commit=True):
        """Atualiza os dados do usuário e reaplica o hash da senha somente se uma nova senha for fornecida."""
        usuario = super().save(commit=False)

        if self.cleaned_data.get("nova_senha"):
            usuario.set_password(self.cleaned_data["nova_senha"])

        if commit:
            usuario.save()

        return usuario


class FormularioPerfil(FormularioEstilizado, forms.ModelForm):
    """
    Formulário de autoatendimento onde o próprio usuário atualiza seus dados
    pessoais e pode opcionalmente alterar sua senha.
    """
    nova_senha = forms.CharField(
        label="Nova senha",
        required=False,
        widget=forms.PasswordInput,
        validators=[validate_password],
        help_text="Deixe em branco para manter a senha atual.",
    )

    confirmar_senha = forms.CharField(
        label="Confirmar nova senha",
        required=False,
        widget=forms.PasswordInput
    )

    class Meta:
        model = Usuario
        fields = ("first_name", "last_name", "email")
        labels = {"first_name": "Nome", "last_name": "Sobrenome"}

    def clean(self):
        """Garante a coincidência das senhas quando a troca de senha é solicitada."""
        dados = super().clean()

        if dados.get("nova_senha") != dados.get("confirmar_senha"):
            self.add_error("confirmar_senha", "As senhas não coincidem.")

        return dados

    def save(self, commit=True):
        """Salva as informações do perfil e atualiza a senha caso solicitada."""
        usuario = super().save(commit=False)

        if self.cleaned_data.get("nova_senha"):
            usuario.set_password(self.cleaned_data["nova_senha"])

        if commit:
            usuario.save()

        return usuario