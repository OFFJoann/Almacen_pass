from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.contrib.auth import get_user_model

from apps.licensing.models import License
from apps.licensing.exceptions import LicenseError
from apps.users.views import user_toggle_active


class FakeResp:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data


def _valid_payload(max_users=3, expires_at=None):
    return {
        'valid': True,
        'empresa': 'Acme SAS',
        'licencia': 'LIC-ACME-7F3A9C',
        'max_users': max_users,
        'expires_at': expires_at,
        'installation_id': '',
        'notes': '',
    }


class LicenseApiTest(TestCase):
    def _activate(self, company, key, response_data):
        lic = License.get_instance()
        lic.company = company
        lic.license_key = key
        with patch('requests.post', return_value=FakeResp(200, response_data)):
            valid, payload, error = lic.verify()
        if valid:
            lic.max_users = payload.get('max_users')
            lic.expires_at = None
            lic.is_valid = True
            lic.error = ''
            lic.save()
        return valid, error

    def test_api_valid(self):
        valid, _ = self._activate('Acme SAS', 'LIC-ACME-7F3A9C', _valid_payload(5))
        self.assertTrue(valid)
        self.assertEqual(License.get_instance().max_users, 5)

    def test_api_not_found(self):
        valid, error = self._activate('Acme SAS', 'WRONG', {'valid': False, 'error': 'Licencia no encontrada para la empresa indicada'})
        self.assertFalse(valid)
        self.assertIn('no encontrada', error)

    def test_api_expired(self):
        exp = (datetime.now() - timedelta(days=1)).isoformat()
        valid, error = self._activate('Acme SAS', 'LIC-ACME-7F3A9C', {'valid': False, 'error': 'Licencia caducada', 'expires_at': exp})
        self.assertFalse(valid)
        self.assertIn('caducada', error)

    def test_enforcement_blocks_creation(self):
        self._activate('Acme SAS', 'LIC-ACME-7F3A9C', _valid_payload(3))
        User = get_user_model()
        for i in range(3):
            User.objects.create_user(email=f'u{i}@t.com', password='X1234567890!', is_active=True)
        with self.assertRaises(LicenseError):
            User.objects.create_user(email='uX@t.com', password='X1234567890!', is_active=True)

    def test_toggle_active_blocked_when_full(self):
        self._activate('Acme SAS', 'LIC-ACME-7F3A9C', _valid_payload(1))
        User = get_user_model()
        sa = User.objects.create_user(email='sa@t.com', password='X1234567890!', role='superadmin')
        inactive = User.objects.create_user(email='ina@t.com', password='X1234567890!', is_active=False)
        rf = RequestFactory()
        req = rf.post(f'/users/{inactive.pk}/toggle-active/')
        req.user = sa
        req.session = {}
        req._messages = FallbackStorage(req)
        user_toggle_active(req, inactive.pk)
        inactive.refresh_from_db()
        self.assertFalse(inactive.is_active)

    def test_sso_respects_limit(self):
        self._activate('Acme SAS', 'LIC-ACME-7F3A9C', _valid_payload(1))
        User = get_user_model()
        User.objects.create_user(email='s1@t.com', password='X1234567890!', is_active=True)
        with self.assertRaises(LicenseError):
            User.objects.get_or_create(email='s2@t.com', defaults={'is_active': True})

    def test_no_license_allows_creation(self):
        self.assertIsNone(License.get_instance().license_key or None)
        User = get_user_model()
        u = User.objects.create_user(email='free@t.com', password='X1234567890!', is_active=True)
        self.assertTrue(u.pk)

    def test_status_uses_stored_values(self):
        # status() no debe llamar la API; usa lo guardado.
        self._activate('Acme SAS', 'LIC-ACME-7F3A9C', _valid_payload(10))
        st = License.get_instance().status()
        self.assertTrue(st['valid'])
        self.assertEqual(st['max_users'], 10)
        self.assertEqual(st['used'], 0)  # aun no se crean usuarios
