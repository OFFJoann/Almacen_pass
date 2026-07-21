from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User


@receiver(post_save, sender=User)
def handle_new_user(sender, instance, created, **kwargs):
    if created:
        from apps.audit.models import AuditLog
        AuditLog.objects.create(
            user=instance,
            action='USER_CREATED',
            details=f'Usuario {instance.email} fue creado',
            result='success'
        )
