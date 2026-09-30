from .models import Alert


def unread_alert_count(request):
    """
    Context Processor do Django responsável por calcular a quantidade de alertas
    não lidos do usuário autenticado e disponibilizá-la globalmente nos templates
    (por exemplo, para exibição de badges e notificações no header/menu).
    """
    # 1. Caso o usuário não esteja autenticado, retorna zero alertas pendentes
    if not request.user.is_authenticated:
        return {"unread_alert_count": 0}
        
    # 2. Define o escopo de visibilidade:
    # Membros da equipe/staff (`is_staff=True`) contabilizam alertas globais de todo o sistema.
    # Usuários comuns contabilizam apenas os alertas atrelados às suas próprias capturas.
    alerts = Alert.objects.all() if request.user.is_staff else Alert.objects.filter(capture__user=request.user)
    
    # 3. Retorna a contagem apenas dos alertas que ainda não foram visualizados (`viewed=False`)
    return {"unread_alert_count": alerts.filter(viewed=False).count()}