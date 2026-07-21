import pyotp
import qrcode
import io
import base64
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView
from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from django_ratelimit.decorators import ratelimit
from django.http import JsonResponse, HttpResponseRedirect
from django.conf import settings

from .forms import LoginForm, MFAForm, MFASetupForm, PasswordResetRequestForm, SetPasswordForm
from .utils import parse_user_agent, get_client_ip
from apps.users.models import User, LoginHistory, ActiveSession


@never_cache
@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def login_view(request):
    if request.user.is_authenticated:
        return redirect('passwords:vault')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()

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

            ActiveSession.objects.filter(
                user=user, user_agent=user_agent
            ).exclude(session_key=request.session.session_key).delete()

            ActiveSession.objects.update_or_create(
                user=user,
                session_key=request.session.session_key,
                defaults={
                    'ip_address': ip,
                    'user_agent': user_agent,
                    'browser': parsed['browser'],
                    'os': parsed['os'],
                    'device': parsed['device'],
                    'last_activity': timezone.now(),
                    'expires_at': timezone.now() + timezone.timedelta(seconds=session_expiry),
                }
            )

            User.objects.filter(pk=user.pk).update(
                last_login=timezone.now(),
                last_login_ip=ip,
                last_login_user_agent=user_agent
            )

            if user.force_password_change:
                return redirect('authentication:force_password_change')

            messages.success(request, _(f'¡Bienvenido de nuevo, {user.full_name}!'))
            next_url = request.GET.get('next', 'passwords:vault')
            return redirect(next_url)
        else:
            messages.error(request, _('Correo o contraseña inválidos'))
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

                login(request, user)
                request.session.set_expiry(session_expiry)
                request.session['mfa_verified'] = True

                ActiveSession.objects.filter(
                    user=user, user_agent=user_agent
                ).exclude(session_key=request.session.session_key).delete()

                ActiveSession.objects.update_or_create(
                    user=user,
                    session_key=request.session.session_key,
                    defaults={
                        'ip_address': ip,
                        'user_agent': user_agent,
                        'browser': parsed['browser'],
                        'os': parsed['os'],
                        'device': parsed['device'],
                        'is_mfa_verified': True,
                        'last_activity': timezone.now(),
                        'expires_at': timezone.now() + timezone.timedelta(seconds=session_expiry),
                    }
                )

                User.objects.filter(pk=user.pk).update(last_login=timezone.now(), last_login_ip=ip)

                del request.session['mfa_user_id']
                del request.session['mfa_remember']

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
