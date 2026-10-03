from django import forms
from .models import Captura


class FormularioCaptura(forms.ModelForm):
    """
    Formulário web para criação e upload manual de capturas no sistema.
    Além dos campos do modelo Captura, inclui campos virtuais não persistes diretamente
    para receber medições dos sensores ambientais (temperatura e umidade).
    """
    # Campos virtuais/adicionais para entrada das leituras de sensores ambientais
    temperatura = forms.DecimalField(
        label="Temperatura (°C)", 
        required=False, 
        min_value=0, 
        max_value=60
    )

    umidade = forms.DecimalField(
        label="Umidade (%)", 
        required=False, 
        min_value=0, 
        max_value=100
    )

    class Meta:
        model = Captura
        fields = ("imagem", "origem", "observacao")
        # Customização do widget para o campo de observação limitando o tamanho inicial da caixa de texto
        widgets = {"observacao": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        """
        Sobrescreve a inicialização do formulário para customizar opções de escolha
        e aplicar classes CSS do Bootstrap em todos os campos dinamicamente.
        """
        super().__init__(*args, **kwargs)

        # Recompõe os rótulos/opções amigáveis exibidos no campo de escolha de origem
        self.fields["origem"].choices = (
            ("manual", "Manual"),
            ("simulado", "Sistema"),
            ("esp32", "Dispositivo"),
        )

        # Injeta automaticamente classes do Bootstrap (form-control / form-select) no HTML dos widgets
        for campo in self.fields.values():
            campo.widget.attrs["class"] = (
                "form-control" if not isinstance(campo.widget, forms.Select) else "form-select"
            )

    def clean(self):
        """
        Validação cruzada de múltiplos campos do formulário.
        Garante a regra de integridade das leituras ambientais: ambos os campos
        (temperatura e umidade) devem ser informados juntos ou ambos mantidos em branco.
        """
        dados = super().clean()

        informados = [
            dados.get("temperatura") is not None, 
            dados.get("umidade") is not None
        ]

        # Lógica XOR / integridade parcial: se um foi preenchido, o outro se torna obrigatório
        if any(informados) and not all(informados):
            raise forms.ValidationError("Informe temperatura e umidade juntas ou deixe ambas vazias.")

        return dados

    def clean_imagem(self):
        """
        Validação individual para o campo de imagem.
        Garante que o arquivo enviado seja estritamente do tipo MIME JPEG/JPG.
        """
        imagem = self.cleaned_data.get("imagem")

        # Verifica o Content-Type do arquivo enviado no upload
        if imagem and getattr(imagem, "content_type", "") not in ("image/jpeg", "image/jpg"):
            raise forms.ValidationError("Envie uma imagem JPEG ou JPG.")

        return imagem