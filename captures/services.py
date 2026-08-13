import random
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.db import transaction

from alerts.models import Alert
from predictions.models import Prediction
from predictions.services import CLASSES_TOMATE, gerar_leitura_ambiental, processar_captura
from sensors.models import EnvironmentalReading

from .models import Capture


def _fotos_demonstrativas():
    pasta = Path(settings.BASE_DIR) / "fotos_nao_controladas"
    return sorted(arquivo for arquivo in pasta.glob("*.jpg") if arquivo.is_file())


def inserir_dados_demonstrativos(usuarios, quantidade=12):
    usuarios = list(usuarios)
    fotos = _fotos_demonstrativas()
    gerador = random.Random(2026)
    arquivos_criados = []
    capturas_criadas = 0

    try:
        with transaction.atomic():
            for indice_usuario, usuario in enumerate(usuarios):
                for indice in range(quantidade):
                    captura = Capture.objects.create(
                        user=usuario,
                        origin=Capture.Origin.SIMULATED,
                        observation=f"Amostra demonstrativa {indice + 1}",
                    )
                    if fotos:
                        foto = gerador.choice(fotos)
                        with foto.open("rb") as arquivo:
                            captura.image.save(
                                f"api_simulada_{usuario.pk}_{captura.pk}_{foto.name}",
                                File(arquivo),
                                save=True,
                            )
                        arquivos_criados.append((captura.image.storage, captura.image.name))
                    gerar_leitura_ambiental(captura, gerador=gerador)
                    classe = CLASSES_TOMATE[(indice_usuario * quantidade + indice) % len(CLASSES_TOMATE)]
                    processar_captura(captura, gerador=gerador, classe_prevista=classe)
                    capturas_criadas += 1
    except Exception:
        for armazenamento, nome in arquivos_criados:
            armazenamento.delete(nome)
        raise

    return {"usuarios": len(usuarios), "capturas": capturas_criadas}


def truncar_dados_operacionais():
    imagens = [
        (captura.image.storage, captura.image.name)
        for captura in Capture.objects.exclude(image="").only("image")
        if captura.image.name
    ]
    totais = {
        "capturas": Capture.objects.count(),
        "leituras": EnvironmentalReading.objects.count(),
        "previsoes": Prediction.objects.count(),
        "alertas": Alert.objects.count(),
    }

    with transaction.atomic():
        Alert.objects.all().delete()
        Prediction.objects.all().delete()
        EnvironmentalReading.objects.all().delete()
        Capture.objects.all().delete()
        transaction.on_commit(lambda: _excluir_arquivos(imagens))

    return totais


def _excluir_arquivos(imagens):
    for armazenamento, nome in imagens:
        armazenamento.delete(nome)
