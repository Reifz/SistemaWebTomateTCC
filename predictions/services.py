import random
from decimal import Decimal

from django.db import transaction

from alerts.services import criar_alertas_da_predicao
from captures.models import Capture
from predictions.models import Prediction
from sensors.models import EnvironmentalReading

CLASSES_TOMATE = [
    "Tomato___Bacterial_spot", "Tomato___Early_blight", "Tomato___Late_blight",
    "Tomato___Leaf_Mold", "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites Two-spotted_spider_mite", "Tomato___Target_Spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus", "Tomato___Tomato_mosaic_virus",
    "Tomato___healthy",
]
CLASSE_SAUDAVEL = "Tomato___healthy"


def nivel_confianca(confianca):
    valor = Decimal(str(confianca))
    if valor < 60:
        return Prediction.ConfidenceStatus.LOW
    if valor < 80:
        return Prediction.ConfidenceStatus.MEDIUM
    return Prediction.ConfidenceStatus.HIGH


def gerar_leitura_ambiental(captura, temperatura=None, umidade=None, gerador=None):
    """Gera uma leitura simulada. Troque esta função ao integrar o sensor DHT22."""
    gerador = gerador or random.SystemRandom()
    temperatura = temperatura if temperatura is not None else round(gerador.uniform(18, 35), 2)
    umidade = umidade if umidade is not None else round(gerador.uniform(50, 95), 2)
    return EnvironmentalReading.objects.create(
        capture=captura,
        temperature=temperatura,
        humidity=umidade,
    )


@transaction.atomic
def processar_captura(captura, gerador=None, classe_prevista=None, confianca=None):
    """Simula a IA. Troque o conteúdo desta função pela inferência do modelo real."""
    captura = Capture.objects.select_for_update().get(pk=captura.pk)
    if hasattr(captura, "prediction"):
        return captura.prediction, False

    gerador = gerador or random.SystemRandom()
    classe_prevista = classe_prevista or gerador.choice(CLASSES_TOMATE)
    confianca = Decimal(str(confianca if confianca is not None else round(gerador.uniform(45, 98), 2)))
    alternativas = gerador.sample([classe for classe in CLASSES_TOMATE if classe != classe_prevista], 2)
    restante = max(Decimal("0"), Decimal("100") - confianca)
    segunda_confianca = (restante * Decimal("0.62")).quantize(Decimal("0.01"))
    terceira_confianca = (restante - segunda_confianca).quantize(Decimal("0.01"))
    tres_melhores = [
        {"class": classe_prevista, "confidence": float(confianca)},
        {"class": alternativas[0], "confidence": float(segunda_confianca)},
        {"class": alternativas[1], "confidence": float(terceira_confianca)},
    ]
    predicao = Prediction.objects.create(
        capture=captura, predicted_class=classe_prevista, confidence=confianca,
        top_three=tres_melhores, confidence_status=nivel_confianca(confianca),
    )
    captura.status = Capture.Status.PROCESSED
    captura.save(update_fields=["status"])
    criar_alertas_da_predicao(predicao)
    return predicao, True
