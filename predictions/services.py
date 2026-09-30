import random
from decimal import Decimal

from django.db import transaction

from alerts.services import criar_alertas_da_predicao
from captures.models import Capture
from predictions.models import Prediction
from sensors.models import EnvironmentalReading

# Lista completa de classes suportadas pelo modelo de detecção de doenças em folhas de tomate
CLASSES_TOMATE = [
    "Tomato___Bacterial_spot", "Tomato___Early_blight", "Tomato___Late_blight",
    "Tomato___Leaf_Mold", "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites Two-spotted_spider_mite", "Tomato___Target_Spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus", "Tomato___Tomato_mosaic_virus",
    "Tomato___healthy",
]
CLASSE_SAUDAVEL = "Tomato___healthy"


def nivel_confianca(confianca):
    """
    Classifica a porcentagem de confiança em um status categórico (LOW, MEDIUM ou HIGH)
    conforme as faixas de corte estabelecidas (<60, <80, >=80).
    """
    valor = Decimal(str(confianca))
    if valor < 60:
        return Prediction.ConfidenceStatus.LOW
    if valor < 80:
        return Prediction.ConfidenceStatus.MEDIUM
    return Prediction.ConfidenceStatus.HIGH


def gerar_leitura_ambiental(captura, temperatura=None, umidade=None, gerador=None):
    """
    Gera uma leitura simulada de temperatura e umidade para uma captura.
    Ponto de extensão: substitua o gerador aleatório pela leitura direta do sensor DHT22.
    """
    # Utiliza por padrão o SystemRandom (gerador criptograficamente seguro) para simulação
    gerador = gerador or random.SystemRandom()
    
    # Define valores aleatórios realistas para temperatura (18-35°C) e umidade (50-95%) se não informados
    temperatura = temperatura if temperatura is not None else round(gerador.uniform(18, 35), 2)
    umidade = umidade if umidade is not None else round(gerador.uniform(50, 95), 2)
    
    return EnvironmentalReading.objects.create(
        capture=captura,
        temperature=temperatura,
        humidity=umidade,
    )


@transaction.atomic
def processar_captura(captura, gerador=None, classe_prevista=None, confianca=None):
    """
    Simula o pipeline de inferência de IA para processar uma imagem de captura.
    Executado dentro de uma transação atômica do banco de dados.
    Ponto de extensão: substitua a geração aleatória pela execução real do modelo de Machine Learning.
    """
    # Aplica lock pessimista na linha do banco (select_for_update) para evitar que a mesma captura seja processada concorrentemente
    captura = Capture.objects.select_for_update().get(pk=captura.pk)
    
    # Idempotência: se a captura já possui predição associada, retorna a predição existente e indica que não foi criada uma nova (False)
    if hasattr(captura, "prediction"):
        return captura.prediction, False

    gerador = gerador or random.SystemRandom()
    
    # Define a classe principal e sua probabilidade/confiança
    classe_prevista = classe_prevista or gerador.choice(CLASSES_TOMATE)
    confianca = Decimal(str(confianca if confianca is not None else round(gerador.uniform(45, 98), 2)))
    
    # Escolhe duas classes alternativas distintas da prevista principal
    alternativas = gerador.sample([classe for classe in CLASSES_TOMATE if classe != classe_prevista], 2)
    
    # Distribui a porcentagem restante (100 - confiança principal) entre as duas alternativas secundárias
    restante = max(Decimal("0"), Decimal("100") - confianca)
    segunda_confianca = (restante * Decimal("0.62")).quantize(Decimal("0.01"))
    terceira_confianca = (restante - segunda_confianca).quantize(Decimal("0.01"))
    
    # Constrói o ranking Top 3 da predição
    tres_melhores = [
        {"class": classe_prevista, "confidence": float(confianca)},
        {"class": alternativas[0], "confidence": float(segunda_confianca)},
        {"class": alternativas[1], "confidence": float(terceira_confianca)},
    ]
    
    # Cria o registro da predição no banco de dados
    predicao = Prediction.objects.create(
        capture=captura,
        predicted_class=classe_prevista,
        confidence=confianca,
        top_three=tres_melhores,
        confidence_status=nivel_confianca(confianca),
    )
    
    # Atualiza o status da captura para PROCESSED
    captura.status = Capture.Status.PROCESSED
    captura.save(update_fields=["status"])
    
    # Aciona a verificação e emissão automática de alertas associados à nova predição
    criar_alertas_da_predicao(predicao)
    
    return predicao, True