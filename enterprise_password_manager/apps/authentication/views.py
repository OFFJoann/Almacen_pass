import pyotp
import qrcode
import io
import base64
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
from django.views.decorators.cache import never_cache
from django_ratelimit.decorators import ratelimit
from django.http import JsonResponse, HttpResponseRedirect
from django.conf import settings

from .forms import (LoginForm, MFAForm, MFASetupForm, PasswordResetRequestForm,
                    SetPasswordForm, EmergencyContactForm)
from .utils import parse_user_agent, get_client_ip, user_has_active_session
from apps.users.models import User, LoginHistory, ActiveSession
from apps.mailer.services import notify_event, send_email, get_smtp_settings


@never_cache
@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def login_view(request):
    if request.user.is_authenticated:
        return redirect('passwords:vault')

    if request.method == 'POST':
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

            session_expiry = 3600
            if form.cleaned_data.get('remember_me', False):
                session_expiry = 604800

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
                last_login_user_agent=user_agent
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
                session_expiry = 604800 if remember_me else 3600

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

                User.objects.filter(pk=user.pk).update(last_login=timezone.now(), last_login_ip=ip)

                del request.session['mfa_user_id']
                del request.session['mfa_remember']

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

    logout(request)
    messages.success(request, _('Has cerrado sesión exitosamente'))
    return redirect('authentication:login')


@login_required
def setup_mfa(request):
    user = request.user
    if user.mfa_enabled:
        messages.info(request, _('MFA ya está activado'))
        return redirect('passwords:vault')

    if not user.mfa_secret:
        user.mfa_secret = pyotp.random_base32()
        user.save()

    totp = pyotp.TOTP(user.mfa_secret)
    provisioning_uri = totp.provisioning_uri(user.email, issuer_name='TICOlvidé')

    qr = qrcode.make(provisioning_uri)
    buffer = io.BytesIO()
    qr.save(buffer, format='PNG')
    buffer.seek(0)
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    if request.method == 'POST':
        form = MFASetupForm(request.POST)
        if form.is_valid():
            if totp.verify(form.cleaned_data['code']):
                user.mfa_enabled = True
                user.save()
                messages.success(request, _('MFA se ha activado exitosamente'))
                return redirect('passwords:vault')
            else:
                messages.error(request, _('Código inválido. Intenta de nuevo'))
    else:
        form = MFASetupForm()

    return render(request, 'authentication/setup_mfa.html', {
        'form': form,
        'qr_code': qr_base64,
        'secret': user.mfa_secret,
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
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                link = request.build_absolute_uri(reverse(
                    'authentication:password_reset_confirm',
                    kwargs={'uidb64': uid, 'token': token},
                ))
                sm = get_smtp_settings()
                company = sm.company_name if sm and sm.company_name else 'TICOlvidé'

                if user.can_manage_users() and user.has_emergency_contact():
                    html = (
                        '<h2>Recuperación de contraseña</h2>'
                        f'<p>Hola {user.emergency_contact_name},</p>'
                        f'<p>El administrador <strong>{user.full_name}</strong> ({user.email}) solicitó '
                        f'recuperar su contraseña en {company}.</p>'
                        '<p>Si reconoces esta solicitud, abre el siguiente enlace para completar el '
                        f'restablecimiento de su contraseña:</p>'
                        f'<p><a href="{link}">{link}</a></p>'
                        '<p>Si no la reconoces, ignora este correo.</p>'
                    )
                    text = (
                        'Recuperación de contraseña\n\n'
                        f'Hola {user.emergency_contact_name},\n'
                        f'El administrador {user.full_name} ({user.email}) solicitó recuperar su '
                        f'contraseña en {company}.\n'
                        'Si reconoces esta solicitud, abre el siguiente enlace para completar el '
                        f'restablecimiento:\n{link}\n'
                        'Si no la reconoces, ignora este correo.\n'
                    )
                    send_email(
                        user.emergency_contact_email,
                        _('Solicitud de recuperación de contraseña - {company}').format(company=company),
                        html, text,
                        status='recovery',
                    )
                elif not user.can_manage_users():
                    html = (
                        '<h2>Recuperación de contraseña</h2>'
                        f'<p>Hola {user.full_name},</p>'
                        f'<p>Recibimos una solicitud para recuperar tu contraseña en {company}.</p>'
                        f'<p>Abre el siguiente enlace para restablecerla:</p>'
                        f'<p><a href="{link}">{link}</a></p>'
                        '<p>Si no la solicitaste, ignora este correo.</p>'
                    )
                    text = (
                        'Recuperación de contraseña\n\n'
                        f'Hola {user.full_name},\n'
                        f'Recibimos una solicitud para recuperar tu contraseña en {company}.\n'
                        f'Abre el siguiente enlace para restablecerla:\n{link}\n'
                        'Si no la solicitaste, ignora este correo.\n'
                    )
                    send_email(
                        user.email,
                        _('Recuperación de contraseña - {company}').format(company=company),
                        html, text,
                        status='recovery',
                    )
                elif user.can_manage_users() and not user.has_emergency_contact():
                    LoginHistory.objects.create(
                        user=user,
                        ip_address=get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT', ''),
                        success=False,
                        failure_reason='Recuperación sin contacto de emergencia',
                    )
            messages.success(request, _('Si el correo corresponde a un usuario, se envió una notificación de recuperación.'))
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
            user.emergency_contact_name = form.cleaned_data['emergency_contact_name'].strip()
            user.emergency_contact_email = form.cleaned_data['emergency_contact_email'].strip().lower()
            user.save()
            messages.success(request, _('Contacto de emergencia registrado exitosamente.'))
            return redirect('passwords:vault')
    else:
        form = EmergencyContactForm(initial={
            'emergency_contact_name': user.emergency_contact_name,
            'emergency_contact_email': user.emergency_contact_email,
        })

    return render(request, 'authentication/emergency_contact.html', {'form': form})
