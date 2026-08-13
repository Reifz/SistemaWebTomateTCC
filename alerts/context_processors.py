from .models import Alert


def unread_alert_count(request):
    if not request.user.is_authenticated:
        return {"unread_alert_count": 0}
    alerts = Alert.objects.all() if request.user.is_staff else Alert.objects.filter(capture__user=request.user)
    return {"unread_alert_count": alerts.filter(viewed=False).count()}
