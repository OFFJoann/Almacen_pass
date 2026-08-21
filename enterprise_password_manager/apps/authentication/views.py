import pyotp
import qrcode
import io
import base64
import string
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView
from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.crypto import get_random_string
from django.views.decorators.cache import never_cache
from django_ratelimit.decorators import ratelimit
from django.http import JsonResponse, HttpResponseRedirect
from django.conf import settings

from .forms import (LoginForm, MFAForm, MFASetupForm, PasswordResetRequestForm,
                    SetPasswordForm, EmergencyContactForm)
from .utils import parse_user_agent, get_client_ip, user_has_active_session, mask_email
from apps.users.models import User, LoginHistory, ActiveSession, get_user_effective_policy, LOCAL_LOGIN_LOCK_LIMIT
from apps.audit.models import AuditLog
from apps.mailer.services import notify_event, send_email, get_smtp_settings
from rest_framework.authtoken.models import Token

SESSION_TIMEOUT_SECONDS = 3600

EMERGENCY_PASSWORD_CHARS = string.ascii_letters + string.digits + '!@#$%^&*'


def session_expiry_for(user, remember_me):
    """Duración de la sesión según la política del grupo (días) al usar 'recordarme'."""
    if not remember_me:
        return SESSION_TIMEOUT_SECONDS
    policy = get_user_effective_policy(user)
    days = policy.get('session_days', 7)
    return min(7 * 86400, days * 86400)


@never_cache
@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def login_view(request):
    if request.user.is_authenticated:
        return redirect('passwords:vault')

    if request.method == 'POST':
        email = (request.POST.get('username') or '').strip().lower()
        user = User.objects.filter(email__iexact=email, is_active=True).first()

        # Cuenta bloqueada por intentos fallidos de login local.
        if user and user.failed_local_attempts >= LOCAL_LOGIN_LOCK_LIMIT:
            messages.error(request, _(
                'Tu cuenta está bloqueada por intentos fallidos de inicio de sesión local. '
                'Inicia sesión con SSO o usa el acceso de emergencia para desbloquearla.'
            ))
            return render(request, 'authentication/login.html', {'form': LoginForm(request)})

        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()

            if user_has_active_session(user):
                LoginHistory.objects.create(
                    user=user,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    success=False,
                    failure_reason='Ya existe una sesión activa',
                )
                messages.error(request, _('Ya tienes una sesión activa en otro dispositivo o navegador. Cierra sesión allí antes de volver a entrar.'))
                return render(request, 'authentication/login.html', {'form': form})

            if user.mfa_enabled:
                request.session['mfa_user_id'] = str(user.id)
                request.session['mfa_remember'] = form.cleaned_data.get('remember_me', False)
                return redirect('authentication:mfa_verify')

            user_agent = request.META.get('HTTP_USER_AGENT', '')
            parsed = parse_user_agent(user_agent)
            ip = get_client_ip(request)
            session_key = request.session.session_key

            LoginHistory.objects.create(
                user=user,
                ip_address=ip,
                user_agent=user_agent,
                browser=parsed['browser'],
                os=parsed['os'],
                device=parsed['device'],
                success=True,
                session_key=session_key or '',
            )

            session_expiry = session_expiry_for(user, form.cleaned_data.get('remember_me', False))

            login(request, user)
            request.session.set_expiry(session_expiry)

            ActiveSession.objects.filter(user=user).delete()
            ActiveSession.objects.create(
                user=user,
                session_key=request.session.session_key,
                ip_address=ip,
                user_agent=user_agent,
                browser=parsed['browser'],
                os=parsed['os'],
                device=parsed['device'],
                is_mfa_verified=user.mfa_enabled,
                last_activity=timezone.now(),
                started_at=timezone.now(),
                expires_at=timezone.now() + timezone.timedelta(seconds=session_expiry),
            )

            User.objects.filter(pk=user.pk).update(
                last_login=timezone.now(),
                last_login_ip=ip,
                last_login_user_agent=user_agent,
                failed_local_attempts=0,
            )

            if user.can_manage_users() and not user.has_emergency_contact():
                messages.info(request, _('Los administradores deben registrar un contacto de emergencia para poder recuperar su contraseña.'))
                return redirect('authentication:emergency_contact')

            if user.force_password_change:
                return redirect('authentication:force_password_change')

            messages.success(request, _(f'¡Bienvenido de nuevo, {user.full_name}!'))
            next_url = request.GET.get('next', 'passwords:vault')
            return redirect(next_url)
        else:
            # Contar intento fallido solo para cuentas con contraseña local utilizable.
            if user and user.has_usable_password():
                new_attempts = min(user.failed_local_attempts + 1, LOCAL_LOGIN_LOCK_LIMIT)
                User.objects.filter(pk=user.pk).update(failed_local_attempts=new_attempts)
                if new_attempts >= LOCAL_LOGIN_LOCK_LIMIT:
                    ip = get_client_ip(request)
                    user_agent = request.META.get('HTTP_USER_AGENT', '')
                    parsed = parse_user_agent(user_agent)
                    LoginHistory.objects.create(
                        user=user,
                        ip_address=ip,
                        user_agent=user_agent,
                        browser=parsed['browser'],
                        os=parsed['os'],
                        device=parsed['device'],
                        success=False,
                        failure_reason='Cuenta bloqueada por intentos fallidos de login local',
                    )
                    AuditLog.objects.create(
                        user=user,
                        action='ACCOUNT_LOCKED',
                        details='Cuenta bloqueada tras 3 intentos fallidos de inicio de sesión local',
                        result='failure',
                        ip_address=ip,
                    )
                    messages.error(request, _(
                        'Tu cuenta ha sido bloqueada por intentos fallidos de inicio de sesión local. '
                        'Inicia sesión con SSO o usa el acceso de emergencia para desbloquearla.'
                    ))
                    return render(request, 'authentication/login.html', {'form': LoginForm(request)})
            messages.error(request, _('Correo o contraseña inválidos'))
            notify_event('login_failed', {
                'usuario': request.POST.get('username', ''),
                'ip': get_client_ip(request),
            })
    else:
        form = LoginForm()

    return render(request, 'authentication/login.html', {'form': form})


@never_cache
def mfa_verify(request):
    user_id = request.session.get('mfa_user_id')
    if not user_id:
        return redirect('authentication:login')

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return redirect('authentication:login')

    if user_has_active_session(user):
        del request.session['mfa_user_id']
        messages.error(request, _('Ya tienes una sesión activa en otro dispositivo o navegador. Cierra sesión allí antes de volver a entrar.'))
        return redirect('authentication:login')

    if request.method == 'POST':
        form = MFAForm(request.POST)
        if form.is_valid():
            totp = pyotp.TOTP(user.mfa_secret)
            if totp.verify(form.cleaned_data['code']):
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

                remember_me = request.session.get('mfa_remember', False)
                session_expiry = session_expiry_for(user, remember_me)

                user.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, user)
                request.session.set_expiry(session_expiry)
                request.session['mfa_verified'] = True

                ActiveSession.objects.filter(user=user).delete()
                ActiveSession.objects.create(
                    user=user,
                    session_key=request.session.session_key,
                    ip_address=ip,
                    user_agent=user_agent,
                    browser=parsed['browser'],
                    os=parsed['os'],
                    device=parsed['device'],
                    is_mfa_verified=True,
                    last_activity=timezone.now(),
                    started_at=timezone.now(),
                    expires_at=timezone.now() + timezone.timedelta(seconds=session_expiry),
                )

                User.objects.filter(pk=user.pk).update(
                    last_login=timezone.now(), last_login_ip=ip, failed_local_attempts=0
                )

                del request.session['mfa_user_id']
                del request.session['mfa_remember']

                if user.force_password_change:
                    return redirect('authentication:force_password_change')

                if user.can_manage_users() and not user.has_emergency_contact():
                    messages.info(request, _('Los administradores deben registrar un contacto de emergencia para poder recuperar su contraseña.'))
                    return redirect('authentication:emergency_contact')

                messages.success(request, _(f'¡Bienvenido de nuevo, {user.full_name}!'))
                return redirect('passwords:vault')
            else:
                messages.error(request, _('Código de autenticación inválido'))
    else:
        form = MFAForm()

    return render(request, 'authentication/mfa_verify.html', {'form': form})


@login_required
def logout_view(request):
    user = request.user
    session_key = request.session.session_key

    LoginHistory.objects.filter(
        user=user, session_key=session_key, logout_at__isnull=True
    ).update(logout_at=timezone.now())

    ActiveSession.objects.filter(user=user, session_key=session_key).delete()

    # Invalida los tokens de la extensión para que el logout web también la cierre.
    Token.objects.filter(user=user).delete()

    logout(request)
    messages.success(request, _('Has cerrado sesión exitosamente'))
    return redirect('authentication:login')


@login_required
def setup_mfa(request):
    user = request.user

    if request.GET.get('cancel') == '1':
        # Cancelar la reconfiguración: se borra el estado en sesión y se
        # conserva el secreto MFA anterior (nunca se sobrescribe hasta verificar).
        request.session.pop('mfa_pending_secret', None)
        request.session.pop('mfa_reconfiguring', None)
        return redirect('authentication:setup_mfa')

    reconfigure = bool(request.session.get('mfa_reconfiguring')) and user.mfa_enabled
    if request.GET.get('reconfigure') == '1' and user.mfa_enabled:
        reconfigure = True
        request.session['mfa_reconfiguring'] = True

    if reconfigure:
        # Reconfigurar: generamos un secreto nuevo pero NO sobrescribimos el
        # actual hasta verificar el código (evita quedarse bloqueado si abandona).
        pending_secret = request.session.get('mfa_pending_secret')
        if not pending_secret:
            pending_secret = pyotp.random_base32()
            request.session['mfa_pending_secret'] = pending_secret
        secret_to_show = pending_secret
        show_setup = True
    elif user.mfa_enabled:
        # Ya activado y solo consulta el estado: no mostramos el QR.
        show_setup = False
        secret_to_show = None
    else:
        if not user.mfa_secret:
            user.mfa_secret = pyotp.random_base32()
            user.save()
        secret_to_show = user.mfa_secret
        show_setup = True

    qr_base64 = None
    if show_setup:
        totp = pyotp.TOTP(secret_to_show)
        provisioning_uri = totp.provisioning_uri(user.email, issuer_name='TICO BOX')
        qr = qrcode.make(provisioning_uri)
        buffer = io.BytesIO()
        qr.save(buffer, format='PNG')
        buffer.seek(0)
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()
    else:
        totp = None

    if request.method == 'POST' and show_setup:
        form = MFASetupForm(request.POST)
        if form.is_valid() and totp and totp.verify(form.cleaned_data['code']):
            user.mfa_secret = secret_to_show
            user.mfa_enabled = True
            user.save()
            request.session.pop('mfa_pending_secret', None)
            request.session.pop('mfa_reconfiguring', None)
            if reconfigure:
                messages.success(request, _('MFA se ha reconfigurado exitosamente'))
            else:
                messages.success(request, _('MFA se ha activado exitosamente'))
            return redirect('passwords:vault')
        else:
            messages.error(request, _('Código inválido. Intenta de nuevo'))
    else:
        form = MFASetupForm()

    return render(request, 'authentication/setup_mfa.html', {
        'form': form,
        'qr_code': qr_base64,
        'secret': secret_to_show,
        'show_setup': show_setup,
        'reconfigure': reconfigure,
        'mfa_enabled': user.mfa_enabled,
    })


@login_required
def disable_mfa(request):
    if request.method == 'POST':
        user = request.user
        user.mfa_enabled = False
        user.mfa_secret = ''
        user.save()
        messages.success(request, _('MFA se ha desactivado'))
    return redirect('passwords:vault')


@login_required
def force_password_change_view(request):
    if not request.user.force_password_change:
        return redirect('passwords:vault')

    if request.method == 'POST':
        form = SetPasswordForm(request.POST)
        if form.is_valid():
            user = request.user
            user.set_password(form.cleaned_data['password'])
            user.force_password_change = False
            user.save()
            update_session_auth_hash(request, user)
            messages.success(request, _('Contraseña cambiada exitosamente'))
            return redirect('passwords:vault')
    else:
        form = SetPasswordForm()

    return render(request, 'authentication/force_password_change.html', {'form': form})


@login_required
def lockout_view(request):
    return render(request, 'authentication/lockout.html')


@never_cache
def password_reset_request(request):
    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].strip().lower()
            user = User.objects.filter(email__iexact=email, is_active=True).first()
            if user:
                sm = get_smtp_settings()
                company = sm.company_name if sm and sm.company_name else 'TICO BOX'
                login_url = request.build_absolute_uri(reverse('authentication:login'))

                # Usuarios estándar: solo SSO, sin recuperación de contraseña local.
                # No se muestra nada; se redirige directo al inicio de sesión.
                if not user.can_manage_users():
                    return redirect('authentication:login')

                if not user.has_emergency_contact():
                    messages.error(request, _(
                        'Tu cuenta no tiene un contacto de emergencia configurado. '
                        'Contacta a un SuperAdmin para habilitar el acceso de emergencia.'
                    ))
                    return redirect('authentication:password_reset_request')

                # Acceso de emergencia: generamos una contraseña local temporal y se la
                # enviamos al contacto de emergencia (no al administrador).
                temp_password = get_random_string(16, allowed_chars=EMERGENCY_PASSWORD_CHARS)
                user.set_password(temp_password)
                user.force_password_change = True
                user.failed_local_attempts = 0
                user.save()

                masked = mask_email(user.emergency_contact_email)
                html = (
                    f'<h2>Acceso de emergencia - {company}</h2>'
                    f'<p>Hola {user.emergency_contact_name},</p>'
                    f'<p>Se solicitó un acceso de emergencia para el administrador '
                    f'<strong>{user.full_name}</strong> ({user.email}) en {company}.</p>'
                    f'<p>Si reconoces esta solicitud, comparte las siguientes credenciales con el '
                    f'administrador para que pueda iniciar sesión localmente (por ejemplo, si el SSO falla):</p>'
                    f'<ul>'
                    f'<li><strong>Correo:</strong> {user.email}</li>'
                    f'<li><strong>Contraseña temporal:</strong> {temp_password}</li>'
                    f'</ul>'
                    f'<p>Inicia sesión en: <a href="{login_url}">{login_url}</a></p>'
                    f'<p>Al entrar se le pedirá cambiar la contraseña temporal.</p>'
                    f'<p>Si no reconoces esta solicitud, ignora este correo y avisa al equipo de seguridad.</p>'
                )
                text = (
                    f'Acceso de emergencia - {company}\n\n'
                    f'Hola {user.emergency_contact_name},\n'
                    f'Se solicitó un acceso de emergencia para el administrador {user.full_name} '
                    f'({user.email}) en {company}.\n\n'
                    f'Credenciales para inicio de sesión local:\n'
                    f'Correo: {user.email}\n'
                    f'Contraseña temporal: {temp_password}\n\n'
                    f'Inicia sesión en: {login_url}\n'
                    f'Al entrar se pedirá cambiar la contraseña temporal.\n'
                )
                send_email(
                    user.emergency_contact_email,
                    _('Acceso de emergencia - {company}').format(company=company),
                    html, text,
                    status='recovery',
                )
                LoginHistory.objects.create(
                    user=user,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    success=True,
                    failure_reason='Solicitud de acceso de emergencia',
                )
                messages.success(request, _(
                    'Te enviamos un correo a tu usuario de emergencia {masked} con las instrucciones '
                    'y credenciales de acceso de emergencia.'
                ).format(masked=masked))
                return redirect('authentication:login')
            messages.success(request, _(
                'Si el correo corresponde a un usuario, se envió una notificación de recuperación.'
            ))
            return redirect('authentication:login')
    else:
        form = PasswordResetRequestForm()

    return render(request, 'authentication/password_reset_request.html', {'form': form})


@never_cache
def password_reset_confirm(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    valid = user is not None and user.is_active and default_token_generator.check_token(user, token)
    if not valid:
        messages.error(request, _('El enlace de recuperación no es válido o ya fue usado. Solicita uno nuevo.'))
        return redirect('authentication:password_reset_request')

    if request.method == 'POST':
        form = SetPasswordForm(request.POST)
        if form.is_valid():
            user.set_password(form.cleaned_data['password'])
            user.force_password_change = False
            user.save()
            ActiveSession.objects.filter(user=user).delete()
            from apps.audit.models import AuditLog
            AuditLog.objects.create(
                user=user,
                action='PASSWORD_RECOVERED',
                details=f'Password recovered via emergency contact: {user.email}',
                result='success',
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )
            messages.success(request, _('Tu contraseña fue restablecida exitosamente. Ya puedes iniciar sesión.'))
            return redirect('authentication:login')
    else:
        form = SetPasswordForm()

    return render(request, 'authentication/password_reset_confirm.html', {'form': form, 'validlink': True})


@login_required
def set_emergency_contact(request):
    user = request.user
    if not user.can_manage_users():
        return redirect('passwords:vault')

    if request.method == 'POST':
        form = EmergencyContactForm(request.POST)
        if form.is_valid():
            already = user.has_emergency_contact()
            user.emergency_contact_name = form.cleaned_data['emergency_contact_name'].strip()
            user.emergency_contact_email = form.cleaned_data['emergency_contact_email'].strip().lower()
            user.save()
            if already:
                messages.success(request, _('Contacto de emergencia actualizado exitosamente.'))
            else:
                messages.success(request, _('Contacto de emergencia registrado exitosamente.'))
            return redirect('passwords:vault')
    else:
        form = EmergencyContactForm(initial={
            'emergency_contact_name': user.emergency_contact_name,
            'emergency_contact_email': user.emergency_contact_email,
        })

    return render(request, 'authentication/emergency_contact.html', {
        'form': form,
        'has_contact': user.has_emergency_contact(),
    })
