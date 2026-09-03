import time
from django.contrib.auth import get_user_model
from apps.passwords.models import Vault

User = get_user_model()
u = User.objects.filter(is_superuser=True).first()
vault, _ = Vault.objects.get_or_create(user=u)

def timed(label, fn):
    t0 = time.time()
    r = fn()
    print('%-26s %.3f s' % (label, time.time()-t0), flush=True)
    return r

from apps.passwords.forms import PasswordEntryForm

data = {
    'name': 'Servicio Prueba',
    'url': 'https://ejemplo.com',
    'username': 'usuario@test.com',
    'password': 'ClavePrueba123!',
    'notes': 'nota',
    'sensitivity': 'medium',
}
form = timed('build form', lambda: PasswordEntryForm(data=data, user=u))
form.is_valid()
entry = form.save(commit=False)
entry.vault = vault

def set_fields():
    e = entry
    e.set_username(form.cleaned_data.get('username', ''))
    e.set_password(form.cleaned_data.get('password', ''))
    e.set_notes(form.cleaned_data.get('notes', ''))
timed('set_username/set_password/set_notes', set_fields)

timed('entry.save()', lambda: entry.save())
timed('form.save_m2m()', lambda: form.save_m2m())

from apps.audit.models import AuditLog
timed('AuditLog.create', lambda: AuditLog.objects.create(
    user=u, action='PASSWORD_CREATED', details='c', result='success', ip_address='127.0.0.1'))

from apps.mailer.services import notify_event, domain_from_url
timed('notify_event', lambda: notify_event('password_created', {
    'usuario': u.email, 'nombre_servicio': 'x', 'dominio': '#', 'url': '/', 'riesgo_actual': 'M'}))

timed('save_m2m (2da)', lambda: form.save_m2m())
print('entry saved pk=', entry.pk)
