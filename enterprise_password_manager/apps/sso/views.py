import requests
import json
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse, HttpResponse
from django.core.exceptions import PermissionDenied
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import UpdateView
from urllib.parse import parse_qs
from .models import SSOConfiguration, SSOLog
from .forms import SSOConfigurationForm
from apps.users.models import User, LoginHistory, ActiveSession
from apps.authentication.utils import parse_user_agent, get_client_ip


@login_required
def sso_settings(request):
    if not request.user.is_superadmin():
        raise PermissionDenied
    config = SSOConfiguration.objects.first()
    logs = SSOLog.objects.all()[:20]
    return render(request, 'sso/settings.html', {
        'config': config,
        'logs': logs,
    })


@login_required
def sso_configure(request):
    if not request.user.is_superadmin():
        raise PermissionDenied
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
    if not request.user.is_superadmin():
        return JsonResponse({'success': False, 'error': 'No autorizado'}, status=403)
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
    if not request.user.is_superadmin():
        raise PermissionDenied
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


def _sso_error(request, config, action, details, status=400):
    ip = get_client_ip(request)
    if config:
        SSOLog.objects.create(
            config=config,
            action=action,
            details=str(details),
            success=False,
            ip_address=ip,
        )
    return HttpResponse(
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<title>Error SSO</title></head><body style="font-family:sans-serif;padding:2rem">'
        f'<h2>Error de inicio de sesión SSO</h2>'
        f'<p style="color:#b00"><strong>{action}</strong></p>'
        f'<pre style="white-space:pre-wrap;background:#f5f5f5;padding:1rem;border-radius:6px">{details}</pre>'
        '<p><a href="/auth/login/">Volver al inicio de sesión</a></p>'
        '</body></html>',
        status=status,
    )


@csrf_exempt
def sso_callback(request):
    config = SSOConfiguration.objects.filter(is_active=True).first()
    if not config:
        return HttpResponse('SSO no está configurado', status=400)

    error = request.GET.get('error')
    if error:
        return _sso_error(request, config, 'CALLBACK_ERROR', f'Auth error: {error}')

    code = request.GET.get('code')
    if not code:
        return _sso_error(request, config, 'CALLBACK_NO_CODE', 'No se recibió código de autorización')

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
            desc = token_json.get('error_description', token_json.get('error', 'Unknown error'))
            return _sso_error(request, config, 'TOKEN_ERROR', f'Fallo al obtener token: {desc}')

        user_info_url = 'https://graph.microsoft.com/v1.0/me'
        headers = {'Authorization': f'Bearer {token_json["access_token"]}'}
        user_response = requests.get(user_info_url, headers=headers, timeout=10)
        user_data = user_response.json()

        email = user_data.get('userPrincipalName') or user_data.get('mail') or ''
        name = user_data.get('displayName') or (email.split('@')[0] if '@' in email else email)

        if not email:
            return _sso_error(
                request, config, 'NO_EMAIL',
                f'Microsoft no devolvió un correo. Respuesta Graph: {user_data}',
            )

        try:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'full_name': name,
                    'is_active': True,
                }
            )
        except Exception as exc:  # noqa: BLE001
            from apps.licensing.exceptions import LicenseError
            if isinstance(exc, LicenseError):
                return _sso_error(
                    request, config, 'LICENSE_LIMIT',
                    'No se pudo crear tu usuario: se alcanzó el límite de la licencia.',
                )
            raise

        if not user.is_active:
            return _sso_error(request, config, 'USER_INACTIVE', 'Tu cuenta ha sido deshabilitada')

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

        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
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

        if user.force_password_change:
            return redirect('authentication:force_password_change')

        # El login por SSO también sirve para desbloquear la cuenta bloqueada por intentos locales.
        User.objects.filter(pk=user.pk).update(failed_local_attempts=0)

        messages.success(request, _(f'¡Bienvenido, {user.full_name}!'))
        return redirect('passwords:vault')

    except Exception as e:
        return _sso_error(request, config, 'LOGIN_ERROR', f'SSO error: {e}')
