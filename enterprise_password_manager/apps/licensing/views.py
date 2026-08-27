from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import License, _parse_dt
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

        if action == 'sync':
            if not lic.license_key or not lic.company:
                messages.error(request, _('No hay licencia activada para sincronizar.'))
                return redirect('licensing:license')
        else:  # activate
            if not company or not key:
                messages.error(request, _('Ingresa la empresa y la clave de licencia.'))
                return redirect('licensing:license')
            lic.company = company
            lic.license_key = key
            lic.api_url = api_url

        was_valid = lic.is_valid
        valid, error = lic.sync()
        if valid and action == 'activate' and not was_valid:
            lic.activated_at = timezone.now()
            lic.save(update_fields=['activated_at'])
        if valid:
            if action == 'activate':
                messages.success(request, _('Licencia validada correctamente.'))
            else:
                messages.success(request, _('Licencia sincronizada correctamente.'))
        else:
            messages.error(request, _('La licencia no es válida: %s') % error)
        return redirect('licensing:license')

    next_sync = None
    if lic.last_checked_at:
        next_sync = lic.last_checked_at + timezone.timedelta(seconds=lic.sync_interval)
    next_sync_ts = int(next_sync.timestamp()) if next_sync else 0

    return render(request, 'licensing/license.html', {
        'status': lic.status(),
        'company': lic.company,
        'api_url': lic.api_url,
        'installation_id': get_installation_id(),
        'last_checked_at': lic.last_checked_at,
        'sync_interval': lic.sync_interval,
        'next_sync_ts': next_sync_ts,
    })
