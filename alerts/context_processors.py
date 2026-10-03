from .models import Alerta


def quantidade_alertas_nao_lidos(request):
    """
    Context Processor do Django que injeta a contagem de alertas não lidos 
    disponível no contexto global de todos os templates.
    """
    # Se o usuário não estiver autenticado (visitante/deslogado), retorna contagem zerada
    if not request.user.is_authenticated:
        return {"quantidade_alertas_nao_lidos": 0}

    # Se for membro da equipe (staff), acessa todos os alertas do sistema.
    # Caso contrário, filtra apenas os alertas das capturas vinculadas ao usuário logado.
    alertas = Alerta.objects.all() if request.user.is_staff else Alerta.objects.filter(captura__usuario=request.user)

    # Executa a query otimizada no banco (COUNT) filtrando apenas os alertas com visualizado=False
    return {"quantidade_alertas_nao_lidos": alertas.filter(visualizado=False).count()}