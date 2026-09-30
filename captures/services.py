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
    """
    Localiza e retorna uma lista ordenada dos arquivos de imagem (.jpg)
    disponíveis no diretório 'fotos_nao_controladas' para uso como dados de teste.
    """
    pasta = Path(settings.BASE_DIR) / "fotos_nao_controladas"
    return sorted(arquivo for arquivo in pasta.glob("*.jpg") if arquivo.is_file())


def inserir_dados_demonstrativos(usuarios, quantidade=12):
    """
    Popula o banco de dados com capturas simuladas, imagens de amostra,
    leituras ambientais, predições e alertas para os usuários fornecidos.
    
    Utiliza uma semente fixa (2026) para reproduzibilidade dos dados e garante
    que arquivos salvos em disco sejam apagados caso ocorra uma falha na transação.
    """
    usuarios = list(usuarios)
    fotos = _fotos_demonstrativas()
    gerador = random.Random(2026)  # Semente fixa para garantir comportamento determinístico
    arquivos_criados = []
    capturas_criadas = 0

    try:
        # Garante que a criação de todos os registros seja atômica
        with transaction.atomic():
            for indice_usuario, usuario in enumerate(usuarios):
                for indice in range(quantidade):
                    # Cria o registro base da captura
                    captura = Capture.objects.create(
                        user=usuario,
                        origin=Capture.Origin.SIMULATED,
                        observation=f"Amostra demonstrativa {indice + 1}",
                    )
                    
                    # Associa uma imagem física aleatória à captura se houver fotos disponíveis
                    if fotos:
                        foto = gerador.choice(fotos)
                        with foto.open("rb") as arquivo:
                            captura.image.save(
                                f"api_simulada_{usuario.pk}_{captura.pk}_{foto.name}",
                                File(arquivo),
                                save=True,
                            )
                        # Registra o armazenamento e nome do arquivo criado para limpeza em caso de erro
                        arquivos_criados.append((captura.image.storage, captura.image.name))
                    
                    # Gera leituras simuladas de temperatura/umidade
                    gerar_leitura_ambiental(captura, gerador=gerador)
                    
                    # Alterna ciclicamente entre as classes de doenças do tomate
                    classe = CLASSES_TOMATE[(indice_usuario * quantidade + indice) % len(CLASSES_TOMATE)]
                    
                    # Simula a inferência do modelo e gera a predição com os alertas associados
                    processar_captura(captura, gerador=gerador, classe_prevista=classe)
                    capturas_criadas += 1

    except Exception:
        # Tratamento de exceção: remove do armazenamento de mídias os arquivos salvos antes da falha
        for armazenamento, nome in arquivos_criados:
            armazenamento.delete(nome)
        raise

    return {"usuarios": len(usuarios), "capturas": capturas_criadas}


def truncar_dados_operacionais():
    """
    Remove todos os dados operacionais (Alertas, Predições, Leituras e Capturas) do banco de dados.
    Garante que as imagens físicas em disco só sejam excluídas após a confirmação (commit) da transação.
    """
    # Mapeia previamente os arquivos físicos armazenados nas capturas que possuem imagem
    imagens = [
        (captura.image.storage, captura.image.name)
        for captura in Capture.objects.exclude(image="").only("image")
        if captura.image.name
    ]
    
    # Contabiliza o total de registros que serão deletados para retorno/auditoria
    totais = {
        "capturas": Capture.objects.count(),
        "leituras": EnvironmentalReading.objects.count(),
        "previsoes": Prediction.objects.count(),
        "alertas": Alert.objects.count(),
    }

    with transaction.atomic():
        # Exclusão em cascata controlada no banco de dados
        Alert.objects.all().delete()
        Prediction.objects.all().delete()
        EnvironmentalReading.objects.all().delete()
        Capture.objects.all().delete()
        
        # O agendamento via `on_commit` garante que os arquivos só serão apagados do disco
        # se a transação do banco for concluída com sucesso (evita perda de mídias caso ocorra rollback)
        transaction.on_commit(lambda: _excluir_arquivos(imagens))

    return totais


def _excluir_arquivos(imagens):
    """Função auxiliar que executa a exclusão dos arquivos físicos de imagem no storage."""
    for armazenamento, nome in imagens:
        armazenamento.delete(nome)