from django import forms
from .models import Capture


class FormularioCaptura(forms.ModelForm):
    temperature = forms.DecimalField(label="Temperatura (°C)", required=False, min_value=-50, max_value=80)
    humidity = forms.DecimalField(label="Umidade (%)", required=False, min_value=0, max_value=100)

    class Meta:
        model = Capture
        fields = ("image", "origin", "observation")
        widgets = {"observation": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["origin"].choices = (("manual", "Manual"), ("simulado", "Sistema"), ("esp32", "Dispositivo"))
        for campo in self.fields.values():
            campo.widget.attrs["class"] = "form-control" if not isinstance(campo.widget, forms.Select) else "form-select"

    def clean(self):
        dados = super().clean()
        informados = [dados.get("temperature") is not None, dados.get("humidity") is not None]
        if any(informados) and not all(informados):
            raise forms.ValidationError("Informe temperatura e umidade juntas ou deixe ambas vazias.")
        return dados
