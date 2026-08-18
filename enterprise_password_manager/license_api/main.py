import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
# Ruta del JSON de licencias. Se puede sobreescribir con la variable de entorno LICENSES_FILE.
LICENSES_FILE = os.environ.get('LICENSES_FILE', str(BASE_DIR / 'licenses.json'))

app = FastAPI(title='EPM License API', version='1.0.0')


class LicenseCheck(BaseModel):
    empresa: str
    licencia: str


def load_licenses():
    try:
        with open(LICENSES_FILE, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []


def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


@app.get('/')
def root():
    return {'name': 'EPM License API', 'version': '1.0.0'}


@app.post('/licencias')
def check_license(payload: LicenseCheck):
    """Valida una licencia para una empresa contra el JSON plano editado por el proveedor."""
    data = load_licenses()
    now = datetime.now()
    for entry in data:
        if entry.get('empresa') == payload.empresa and entry.get('licencia') == payload.licencia:
            if not entry.get('active', True):
                return {'valid': False, 'error': 'Licencia inactiva', 'empresa': payload.empresa}
            exp = _parse_dt(entry.get('expires_at'))
            if exp and exp < now:
                return {
                    'valid': False,
                    'error': 'Licencia caducada',
                    'empresa': payload.empresa,
                    'expires_at': entry.get('expires_at'),
                }
            return {
                'valid': True,
                'empresa': entry.get('empresa'),
                'licencia': entry.get('licencia'),
                'max_users': entry.get('max_users'),
                'expires_at': entry.get('expires_at'),
                'installation_id': entry.get('installation_id', ''),
                'notes': entry.get('notes', ''),
            }
    return {'valid': False, 'error': 'Licencia no encontrada para la empresa indicada'}


@app.get('/licencias/{empresa}')
def list_company(empresa: str):
    """Expone (sin revelar la clave) las licencias de una empresa para que el tenant las consulte."""
    data = load_licenses()
    result = []
    for entry in data:
        if entry.get('empresa') == empresa:
            result.append({
                'licencia': entry.get('licencia'),
                'max_users': entry.get('max_users'),
                'expires_at': entry.get('expires_at'),
                'active': entry.get('active', True),
            })
    return {'empresa': empresa, 'licenses': result}
