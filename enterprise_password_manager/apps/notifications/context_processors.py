from .models import Notification


def notification_count(request):
    if request.user.is_authenticated:
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return {'unread_notifications': count}
    return {'unread_notifications': 0}
