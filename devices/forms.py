from django import forms

from .models import Dispositivo


class FormularioDispositivo(forms.ModelForm):
    class Meta:
        model = Dispositivo
        fields = ("identificador", "nome", "usuario", "localizacao", "status")
        labels = {
            "identificador": "Identificador",
            "nome": "Nome",
            "usuario": "Responsável",
            "localizacao": "Localização",
            "status": "Situação",
        }
        help_texts = {
            "identificador": "Use o código informado pelo dispositivo, por exemplo: ESTUFA-01.",
        }

    def clean_identificador(self):
        return self.cleaned_data["identificador"].strip().upper()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for campo in self.fields.values():
            campo.widget.attrs["class"] = "form-select" if isinstance(campo.widget, forms.Select) else "form-control"
