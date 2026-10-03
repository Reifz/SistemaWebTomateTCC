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
    """
    Função utilitária interna para listar e ordenar todas as imagens JPEG (.jpg)
    disponíveis na pasta 'fotos_nao_controladas' no diretório raiz do projeto.
    """
    pasta = Path(settings.BASE_DIR) / "fotos_nao_controladas"

    return sorted(arquivo for arquivo in pasta.glob("*.jpg") if arquivo.is_file())


def inserir_dados_demonstrativos(usuarios, quantidade=12):
    """
    Gera e popula massa de dados demonstrativos/fictícios no sistema para uma lista de usuários.
    
    Para cada usuário, cria o número especificado de capturas simuladas, seleciona aleatoriamente
    uma imagem de amostra, gera medições de sensores (temperatura/umidade) e dispara o pipeline
    de inferência da IA (processar_captura).
    
    Conta com rollback manual de arquivos armazenados no disco em caso de falha/exceção.
    """
    usuarios = list(usuarios)

    fotos = _fotos_demonstrativas()

    # Define uma semente (seed) fixa para garantir repetibilidade na seleção aleatória das fotos
    gerador = random.Random(2026)

    # Lista para registrar os arquivos salvos no storage durante a execução
    arquivos_criados = []

    capturas_criadas = 0

    try:
        for usuario in usuarios:

            for indice in range(quantidade):
                # Instancia a captura inicial vinculada ao usuário com origem simulada
                captura = Captura.objects.create(
                    usuario=usuario,
                    origem=Captura.Origem.SIMULADA,
                    observacao=f"Amostra demonstrativa {indice + 1}",
                )

                # Se existirem fotos no diretório, seleciona uma e salva no campo FileField
                if fotos:
                    foto = gerador.choice(fotos)

                    with foto.open("rb") as arquivo:
                        captura.imagem.save(
                            f"api_simulada_{usuario.pk}_{captura.pk}_{foto.name}",
                            File(arquivo),
                            save=True,
                        )

                    # Registra a referência do storage e o nome do arquivo salvo
                    arquivos_criados.append((captura.imagem.storage, captura.imagem.name))

                # Gera medições simuladas de sensores para a captura
                gerar_leitura_ambiental(captura, gerador=gerador)

                # Dispara o processamento e predição do modelo de IA para a captura
                processar_captura(captura)

                capturas_criadas += 1

    except Exception:
        # Se ocorrer qualquer erro na geração, remove todos os arquivos já salvos no disco
        for armazenamento, nome in arquivos_criados:
            armazenamento.delete(nome)

        # Reevoca a exceção para ser tratada em camadas superiores
        raise

    return {"usuarios": len(usuarios), "capturas": capturas_criadas}


def truncar_dados_operacionais():
    """
    Realiza o expurgo/limpeza completa de todos os dados operacionais do sistema
    (Alertas, Predições, Leituras Ambientais e Capturas), além de apagar os arquivos
    de imagem armazenados no sistema de arquivos.
    
    Utiliza transação atômica no banco de dados e adia a remoção física dos arquivos
    para o momento pós-commit (`transaction.on_commit`), evitando a perda acidental
    de imagens caso o banco sofra um rollback.
    """
    # Mapeia previamente todos os arquivos físicos associados às capturas existentes
    imagens = [
        (captura.imagem.storage, captura.imagem.name)
        for captura in Captura.objects.exclude(imagem="").only("imagem")
        if captura.imagem.name
    ]

    # Armazena os totais de registros antes da exclusão para relatórios/mensagens
    totais = {
        "capturas": Captura.objects.count(),
        "leituras": LeituraAmbiental.objects.count(),
        "previsoes": Predicao.objects.count(),
        "alertas": Alerta.objects.count(),
    }

    with transaction.atomic():
        # Remove os registros do banco de dados na ordem respeitando as chaves estrangeiras
        Alerta.objects.all().delete()

        Predicao.objects.all().delete()

        LeituraAmbiental.objects.all().delete()

        Captura.objects.all().delete()

        # Garante que os arquivos físicos só sejam apagados no disco após o sucesso do commit da transação
        transaction.on_commit(lambda: _excluir_arquivos(imagens))

    return totais


def _excluir_arquivos(imagens):
    """
    Função utilitária interna para apagar do storage a lista de arquivos de imagem especificada.
    """
    for armazenamento, nome in imagens:
        armazenamento.delete(nome)