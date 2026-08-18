from apps.users.models import get_user_effective_policy


def export_policy(request):
    if request.user.is_authenticated:
        policy = get_user_effective_policy(request.user)
        return {'allow_export': policy.get('allow_export', True)}
    return {'allow_export': False}
