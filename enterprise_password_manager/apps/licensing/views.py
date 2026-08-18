from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import License
from .utils import get_installation_id


@login_required
def license_view(request):
    if not request.user.is_superadmin():
        raise PermissionDenied

    lic = License.get_instance()

    if request.method == 'POST':
        action = request.POST.get('action', 'activate')
        company = request.POST.get('company', '').strip()
        key = request.POST.get('license_key', '').strip()
        api_url = request.POST.get('api_url', '').strip()

        if action == 'revalidate':
            if not lic.license_key or not lic.company:
                messages.error(request, _('No hay licencia activada para revalidar.'))
                return redirect('licensing:license')
        else:
            if not company or not key:
                messages.error(request, _('Ingresa la empresa y la clave de licencia.'))
                return redirect('licensing:license')
            lic.company = company
            lic.license_key = key
            lic.api_url = api_url

        valid, payload, error = lic.verify()
        if valid:
            lic.max_users = payload.get('max_users')
            lic.expires_at = _parse_dt(payload.get('expires_at'))
            lic.installation_id = payload.get('installation_id', '') or ''
            lic.is_valid = True
            lic.error = ''
            lic.last_checked_at = timezone.now()
            if action != 'revalidate':
                lic.activated_at = timezone.now()
            lic.save()
            messages.success(request, _('Licencia validada correctamente.'))
        else:
            lic.is_valid = False
            lic.error = error
            lic.last_checked_at = timezone.now()
            lic.save(update_fields=['is_valid', 'error', 'last_checked_at'])
            messages.error(request, _('La licencia no es válida: %s') % error)
        return redirect('licensing:license')

    return render(request, 'licensing/license.html', {
        'status': lic.status(),
        'company': lic.company,
        'api_url': lic.api_url,
        'installation_id': get_installation_id(),
    })


def _parse_dt(value):
    from django.utils.dateparse import parse_datetime
    if not value:
        return None
    return parse_datetime(value)
