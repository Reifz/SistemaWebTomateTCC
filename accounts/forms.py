from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

Usuario = get_user_model()


class FormularioEstilizado:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs["class"] = "form-check-input" if isinstance(campo.widget, forms.CheckboxInput) else "form-control"


class FormularioCriacaoUsuario(FormularioEstilizado, forms.ModelForm):
    password1 = forms.CharField(label="Senha", widget=forms.PasswordInput, validators=[validate_password])
    password2 = forms.CharField(label="Confirmar senha", widget=forms.PasswordInput)

    class Meta:
        model = Usuario
        fields = ("first_name", "last_name", "email", "is_staff", "is_active")
        labels = {"first_name": "Nome", "last_name": "Sobrenome", "is_staff": "Administrador", "is_active": "Conta ativa"}

    def clean(self):
        dados = super().clean()
        if dados.get("password1") != dados.get("password2"):
            self.add_error("password2", "As senhas não coincidem.")
        return dados

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.set_password(self.cleaned_data["password1"])
        if commit:
            usuario.save()
        return usuario


class FormularioEdicaoUsuario(FormularioEstilizado, forms.ModelForm):
    new_password = forms.CharField(label="Nova senha", required=False, widget=forms.PasswordInput, validators=[validate_password], help_text="Deixe em branco para manter a senha atual.")

    class Meta:
        model = Usuario
        fields = ("first_name", "last_name", "email", "is_staff", "is_active")
        labels = {"first_name": "Nome", "last_name": "Sobrenome", "is_staff": "Administrador", "is_active": "Conta ativa"}

    def __init__(self, *args, usuario_logado=None, **kwargs):
        self.usuario_logado = usuario_logado
        super().__init__(*args, **kwargs)

    def clean(self):
        dados = super().clean()
        if self.instance == self.usuario_logado:
            if not dados.get("is_active"):
                self.add_error("is_active", "Você não pode desativar a própria conta.")
            if not dados.get("is_staff"):
                self.add_error("is_staff", "Você não pode remover seu próprio acesso administrativo.")
        return dados

    def save(self, commit=True):
        usuario = super().save(commit=False)
        if self.cleaned_data.get("new_password"):
            usuario.set_password(self.cleaned_data["new_password"])
        if commit:
            usuario.save()
        return usuario


class FormularioPerfil(FormularioEstilizado, forms.ModelForm):
    nova_senha = forms.CharField(
        label="Nova senha",
        required=False,
        widget=forms.PasswordInput,
        validators=[validate_password],
        help_text="Deixe em branco para manter a senha atual.",
    )
    confirmar_senha = forms.CharField(label="Confirmar nova senha", required=False, widget=forms.PasswordInput)

    class Meta:
        model = Usuario
        fields = ("first_name", "last_name", "email")
        labels = {"first_name": "Nome", "last_name": "Sobrenome"}

    def clean(self):
        dados = super().clean()
        if dados.get("nova_senha") != dados.get("confirmar_senha"):
            self.add_error("confirmar_senha", "As senhas não coincidem.")
        return dados

    def save(self, commit=True):
        usuario = super().save(commit=False)
        if self.cleaned_data.get("nova_senha"):
            usuario.set_password(self.cleaned_data["nova_senha"])
        if commit:
            usuario.save()
        return usuario
