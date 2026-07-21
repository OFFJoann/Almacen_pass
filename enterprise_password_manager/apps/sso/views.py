import requests
import json
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import UpdateView
from urllib.parse import parse_qs
from .models import SSOConfiguration, SSOLog
from .forms import SSOConfigurationForm
from apps.users.models import User, LoginHistory, ActiveSession
from apps.authentication.utils import parse_user_agent, get_client_ip


@login_required
def sso_settings(request):
    config = SSOConfiguration.objects.first()
    logs = SSOLog.objects.all()[:20]
    return render(request, 'sso/settings.html', {
        'config': config,
        'logs': logs,
    })


@login_required
def sso_configure(request):
    config = SSOConfiguration.objects.first()
    if request.method == 'POST':
        form = SSOConfigurationForm(request.POST, instance=config)
        if form.is_valid():
            sso_config = form.save()

            from apps.audit.models import AuditLog
            AuditLog.objects.create(
                user=request.user,
                action='SSO_CONFIGURED',
                details=f'SSO configured for {sso_config.get_provider_display()}',
                result='success',
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )

            messages.success(request, _('Configuración SSO guardada'))
            return redirect('sso:settings')
    else:
        form = SSOConfigurationForm(instance=config)

    return render(request, 'sso/configure.html', {
        'form': form,
        'config': config,
    })


@login_required
def sso_test_connection(request):
    config = SSOConfiguration.objects.first()
    if not config:
        return JsonResponse({'success': False, 'error': 'No se encontró configuración SSO'})

    try:
        url = f'https://login.microsoftonline.com/{config.tenant_id}/v2.0/.well-known/openid-configuration'
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            SSOLog.objects.create(
                config=config,
                action='TEST_CONNECTION',
                details='SSO connection test successful',
                success=True,
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )
            return JsonResponse({'success': True, 'message': 'Conexión exitosa'})
        else:
            return JsonResponse({'success': False, 'error': f'Failed with status {response.status_code}'})
    except Exception as e:
        SSOLog.objects.create(
            config=config,
            action='TEST_CONNECTION',
            details=f'Connection test failed: {str(e)}',
            success=False,
            ip_address=request.META.get('REMOTE_ADDR', ''),
        )
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def sso_toggle(request):
    config = SSOConfiguration.objects.first()
    if not config:
        messages.error(request, _('No se encontró configuración SSO'))
        return redirect('sso:settings')

    if request.method == 'POST':
        config.is_active = not config.is_active
        config.save()

        action = 'SSO_ENABLED' if config.is_active else 'SSO_DISABLED'

        from apps.audit.models import AuditLog
        AuditLog.objects.create(
            user=request.user,
            action=action,
            details=f'SSO {"enabled" if config.is_active else "disabled"}',
            result='success',
            ip_address=request.META.get('REMOTE_ADDR', ''),
        )

        status = 'enabled' if config.is_active else 'disabled'
        messages.success(request, _(f'SSO {status}'))

    return redirect('sso:settings')


def sso_login(request):
    config = SSOConfiguration.objects.filter(is_active=True).first()
    if not config:
        messages.error(request, _('SSO no está configurado'))
        return redirect('authentication:login')

    auth_url = config.get_authorization_url()
    return redirect(auth_url)


@csrf_exempt
def sso_callback(request):
    config = SSOConfiguration.objects.filter(is_active=True).first()
    if not config:
        messages.error(request, _('SSO no está configurado'))
        return redirect('authentication:login')

    code = request.GET.get('code')
    error = request.GET.get('error')
    if error:
        SSOLog.objects.create(
            config=config,
            action='CALLBACK_ERROR',
            details=f'Auth error: {error}',
            success=False,
            ip_address=request.META.get('REMOTE_ADDR', ''),
        )
        messages.error(request, _('Autenticación SSO fallida'))
        return redirect('authentication:login')

    if not code:
        messages.error(request, _('No se recibió código de autorización'))
        return redirect('authentication:login')

    try:
        token_url = f'https://login.microsoftonline.com/{config.tenant_id}/oauth2/v2.0/token'
        token_data = {
            'client_id': config.client_id,
            'client_secret': config.client_secret,
            'code': code,
            'redirect_uri': config.redirect_uri,
            'grant_type': 'authorization_code',
            'scope': config.scopes,
        }
        token_response = requests.post(token_url, data=token_data, timeout=10)
        token_json = token_response.json()

        if 'access_token' not in token_json:
            SSOLog.objects.create(
                config=config,
                action='TOKEN_ERROR',
                details=f'Failed to get token: {token_json.get("error_description", "Unknown error")}',
                success=False,
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )
            messages.error(request, _('Error al autenticar con Microsoft'))
            return redirect('authentication:login')

        user_info_url = 'https://graph.microsoft.com/v1.0/me'
        headers = {'Authorization': f'Bearer {token_json["access_token"]}'}
        user_response = requests.get(user_info_url, headers=headers, timeout=10)
        user_data = user_response.json()

        email = user_data.get('userPrincipalName', '') or user_data.get('mail', '')
        name = user_data.get('displayName', email.split('@')[0])

        if not email:
            messages.error(request, _('No se pudo obtener el correo de Microsoft'))
            return redirect('authentication:login')

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'full_name': name,
                'is_active': True,
            }
        )

        if not user.is_active:
            messages.error(request, _('Tu cuenta ha sido deshabilitada'))
            return redirect('authentication:login')

        if config.sync_groups:
            group_ids = user_data.get('groupIds', [])
            if group_ids:
                pass

        user_agent = request.META.get('HTTP_USER_AGENT', '')
        parsed = parse_user_agent(user_agent)
        ip = get_client_ip(request)

        LoginHistory.objects.create(
            user=user,
            ip_address=ip,
            user_agent=user_agent,
            browser=parsed['browser'],
            os=parsed['os'],
            device=parsed['device'],
            success=True,
        )

        login(request, user)
        ActiveSession.objects.update_or_create(
            user=user, session_key=request.session.session_key,
            defaults={
                'ip_address': ip, 'user_agent': user_agent,
                'browser': parsed['browser'], 'os': parsed['os'],
                'device': parsed['device'],
                'expires_at': timezone.now() + timezone.timedelta(hours=1),
            }
        )

        SSOLog.objects.create(
            config=config,
            action='LOGIN_SUCCESS',
            user_email=email,
            details='SSO login successful',
            success=True,
            ip_address=ip,
        )

        messages.success(request, _(f'¡Bienvenido, {user.full_name}!'))
        return redirect('passwords:vault')

    except Exception as e:
        SSOLog.objects.create(
            config=config,
            action='LOGIN_ERROR',
            details=f'SSO error: {str(e)}',
            success=False,
            ip_address=request.META.get('REMOTE_ADDR', ''),
        )
        messages.error(request, _('Autenticación SSO fallida'))
        return redirect('authentication:login')
