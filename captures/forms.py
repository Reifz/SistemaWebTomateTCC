from django import forms
from .models import Captura


class FormularioCaptura(forms.ModelForm):
    temperatura = forms.DecimalField(label="Temperatura (°C)", required=False, min_value=0, max_value=60)

    umidade = forms.DecimalField(label="Umidade (%)", required=False, min_value=0, max_value=100)

    class Meta:
        model = Captura

        fields = ("imagem", "origem", "observacao")

        widgets = {"observacao": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["origem"].choices = (("manual", "Manual"), ("simulado", "Sistema"), ("esp32", "Dispositivo"))

        for campo in self.fields.values():
            campo.widget.attrs["class"] = "form-control" if not isinstance(campo.widget, forms.Select) else "form-select"

    def clean(self):
        dados = super().clean()

        informados = [dados.get("temperatura") is not None, dados.get("umidade") is not None]

        if any(informados) and not all(informados):
            raise forms.ValidationError("Informe temperatura e umidade juntas ou deixe ambas vazias.")

        return dados

    def clean_imagem(self):
        imagem = self.cleaned_data.get("imagem")

        if imagem and getattr(imagem, "content_type", "") not in ("image/jpeg", "image/jpg"):
            raise forms.ValidationError("Envie uma imagem JPEG ou JPG.")

        return imagem
