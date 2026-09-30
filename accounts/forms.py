from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

Usuario = get_user_model()


class FormularioEstilizado:
    """
    Mixin auxiliar para aplicar dinamicamente classes CSS do Bootstrap
    (`form-control` e `form-check-input`) aos widgets dos formulários.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            # Aplica a classe adequada dependendo do tipo do elemento visual (checkbox vs input texto)
            campo.widget.attrs["class"] = (
                "form-check-input" if isinstance(campo.widget, forms.CheckboxInput) else "form-control"
            )


class FormularioCriacaoUsuario(FormularioEstilizado, forms.ModelForm):
    """Formulário administrativo para cadastro de novos usuários com verificação de senha em dois campos."""
    password1 = forms.CharField(
        label="Senha", 
        widget=forms.PasswordInput, 
        validators=[validate_password]
    )
    password2 = forms.CharField(
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
        """Valida se os dois campos de senha preenchidos são exatamente iguais."""
        dados = super().clean()
        if dados.get("password1") != dados.get("password2"):
            self.add_error("password2", "As senhas não coincidem.")
        return dados

    def save(self, commit=True):
        """Sobrescreve a persistência para criptografar a senha (set_password) antes de salvar no banco."""
        usuario = super().save(commit=False)
        usuario.set_password(self.cleaned_data["password1"])
        if commit:
            usuario.save()
        return usuario


class FormularioEdicaoUsuario(FormularioEstilizado, forms.ModelForm):
    """
    Formulário administrativo para edição de usuários com regras de segurança contra
    auto-bloqueio (impede que um admin desative a si próprio ou remova o próprio acesso).
    """
    new_password = forms.CharField(
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
        # Recebe a referência do usuário logado que está realizando a edição
        self.usuario_logado = usuario_logado
        super().__init__(*args, **kwargs)

    def clean(self):
        """Regra de segurança: impede o usuário logado de revogar as próprias permissões ou desativar a si mesmo."""
        dados = super().clean()
        if self.instance == self.usuario_logado:
            if not dados.get("is_active"):
                self.add_error("is_active", "Você não pode desativar a própria conta.")
            if not dados.get("is_staff"):
                self.add_error("is_staff", "Você não pode remover seu próprio acesso administrativo.")
        return dados

    def save(self, commit=True):
        """Atualiza os dados do usuário e altera a senha apenas se o campo 'new_password' for preenchido."""
        usuario = super().save(commit=False)
        if self.cleaned_data.get("new_password"):
            usuario.set_password(self.cleaned_data["new_password"])
        if commit:
            usuario.save()
        return usuario


class FormularioPerfil(FormularioEstilizado, forms.ModelForm):
    """Formulário de autoatendimento para o usuário atualizar suas próprias informações pessoais e senha."""
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
        """Valida a confirmação da nova senha apenas quando a troca é solicitada."""
        dados = super().clean()
        if dados.get("nova_senha") != dados.get("confirmar_senha"):
            self.add_error("confirmar_senha", "As senhas não coincidem.")
        return dados

    def save(self, commit=True):
        """Aplica os dados do perfil e atualiza a senha caso uma nova senha válida tenha sido informada."""
        usuario = super().save(commit=False)
        if self.cleaned_data.get("nova_senha"):
            usuario.set_password(self.cleaned_data["nova_senha"])
        if commit:
            usuario.save()
        return usuario