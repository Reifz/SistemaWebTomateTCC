import random
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.db import transaction

from alerts.models import Alerta
from predictions.models import Predicao
from predictions.services import gerar_leitura_ambiental, processar_captura
from sensors.models import LeituraAmbiental

from .models import Captura


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
        for usuario in usuarios:

            for indice in range(quantidade):
                captura = Captura.objects.create(
                    usuario=usuario,
                    origem=Captura.Origem.SIMULADA,
                    observacao=f"Amostra demonstrativa {indice + 1}",
                )

                if fotos:
                    foto = gerador.choice(fotos)

                    with foto.open("rb") as arquivo:
                        captura.imagem.save(
                            f"api_simulada_{usuario.pk}_{captura.pk}_{foto.name}",
                            File(arquivo),
                            save=True,
                        )

                    arquivos_criados.append((captura.imagem.storage, captura.imagem.name))

                gerar_leitura_ambiental(captura, gerador=gerador)

                processar_captura(captura)

                capturas_criadas += 1

    except Exception:
        for armazenamento, nome in arquivos_criados:
            armazenamento.delete(nome)

        raise

    return {"usuarios": len(usuarios), "capturas": capturas_criadas}


def truncar_dados_operacionais():
    imagens = [
        (captura.imagem.storage, captura.imagem.name)
        for captura in Captura.objects.exclude(imagem="").only("imagem")
        if captura.imagem.name
    ]

    totais = {
        "capturas": Captura.objects.count(),
        "leituras": LeituraAmbiental.objects.count(),
        "previsoes": Predicao.objects.count(),
        "alertas": Alerta.objects.count(),
    }

    with transaction.atomic():
        Alerta.objects.all().delete()

        Predicao.objects.all().delete()

        LeituraAmbiental.objects.all().delete()

        Captura.objects.all().delete()

        # Evita perder as imagens caso o banco reverta a transação.
        transaction.on_commit(lambda: _excluir_arquivos(imagens))

    return totais


def _excluir_arquivos(imagens):
    for armazenamento, nome in imagens:
        armazenamento.delete(nome)
