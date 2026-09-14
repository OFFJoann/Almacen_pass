from .models import Notification


def notification_count(request):
    if request.user.is_authenticated:
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        recent = Notification.objects.filter(user=request.user, is_read=False)[:8]
        return {'unread_notifications': count, 'recent_notifications': recent}
    return {'unread_notifications': 0, 'recent_notifications': []}
