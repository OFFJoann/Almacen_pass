import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', os.getenv('DJANGO_SETTINGS_MODULE', 'config.settings'))
import django
django.setup()

from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from django.db import close_old_connections

from apps.api_tokens.models import ApiToken

from . import schemas
from . import queries

bearer = HTTPBearer(auto_error=False)


def get_admin(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    token: Optional[str] = Query(None, description="Token de API (alternativa a Bearer)"),
):
    key = creds.credentials if creds else token
    if not key:
        raise HTTPException(
            status_code=401,
            detail="Se requiere un token de API (Bearer en Authorization o parámetro ?token=).",
        )
    api_token = ApiToken.objects.select_related("user").filter(key=key).first()
    if not api_token:
        raise HTTPException(status_code=403, detail="Token de API inválido.")
    if not api_token.is_valid:
        raise HTTPException(
            status_code=403,
            detail="Token de API inactivo o caducado.",
        )
    user = api_token.user
    if not user.can_manage_users():
        raise HTTPException(
            status_code=403,
            detail="El token no pertenece a un usuario con permisos de administrador.",
        )
    api_token.mark_used()
    return user


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_old_connections()


app = FastAPI(
    title="EPM Reports API",
    description=(
        "API de reportes empresariales para Enterprise Password Manager. "
        "Expone la información agregada del panel de administración (usuarios, grupos, "
        "riesgo, contraseñas comprometidas, auditoría, intentos de login, almacenamiento y "
        "registros obsoletos) para la generación de informes automatizados.\n\n"
        "Autenticación: usa un API Token generado desde el administración de Django "
        "(sección 'Tokens de API'), enviándolo como `Authorization: Bearer <token>` o "
        "`?token=<token>`. El token debe estar activo, no haber caducado y pertenecer a un "
        "usuario con permisos de administrador."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def close_db_connections(request, call_next):
    try:
        response = await call_next(request)
    finally:
        close_old_connections()
    return response


API_PREFIX = "/api/v1/admin"


@app.get("/", tags=["meta"])
def root():
    return {
        "name": "EPM Reports API",
        "version": "1.0.0",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


@app.get(f"{API_PREFIX}/overview", response_model=schemas.Overview, tags=["panel"])
def get_overview(
    group_id: Optional[str] = Query(None, description="Filtrar por grupo"),
    admin=Depends(get_admin),
):
    """Resumen general de la empresa: usuarios, contraseñas, secretos, MFA, riesgo, robustez y filtraciones."""
    return queries.overview_data(group_id)


@app.get(f"{API_PREFIX}/users", response_model=List[schemas.UserDetail], tags=["usuarios"])
def get_users(
    group_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    admin=Depends(get_admin),
):
    """Listado de usuarios con su riesgo individual calculado."""
    return queries.list_users(group_id, limit, offset)


@app.get(f"{API_PREFIX}/users/{{user_id}}", response_model=schemas.UserDetail, tags=["usuarios"])
def get_user(user_id: str, admin=Depends(get_admin)):
    """Detalle de un usuario, incluyendo su riesgo particular."""
    detail = queries.user_detail(user_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return detail


@app.get(f"{API_PREFIX}/groups", response_model=List[schemas.GroupInfo], tags=["grupos"])
def get_groups(admin=Depends(get_admin)):
    """Grupos de la empresa y sus políticas (longitud mínima, retención, sesión, exportación)."""
    return queries.list_groups()


@app.get(f"{API_PREFIX}/risk", response_model=schemas.RiskSummary, tags=["panel"])
def get_risk(
    group_id: Optional[str] = Query(None),
    admin=Depends(get_admin),
):
    """Riesgo general agregado de la empresa y conteos de usuarios en situación de riesgo."""
    return queries.risk_summary(group_id)


@app.get(f"{API_PREFIX}/darkweb", response_model=List[schemas.DarkwebEntry], tags=["panel"])
def get_darkweb(
    group_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    admin=Depends(get_admin),
):
    """Contraseñas detectadas en filtraciones (dark web) con su propietario."""
    return queries.darkweb_data(group_id, limit)


@app.get(f"{API_PREFIX}/audit", response_model=List[schemas.AuditLogEntry], tags=["auditoría"])
def get_audit(
    user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None, description="Filtrar por tipo de acción, p.ej. PASSWORD_CREATED"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    admin=Depends(get_admin),
):
    """Registro de auditoría de la empresa (acciones, resultados, IP)."""
    return list(queries.audit_data(user_id, action, limit, offset))


@app.get(f"{API_PREFIX}/login-attempts", response_model=List[schemas.LoginAttempt], tags=["auditoría"])
def get_login_attempts(
    user_id: Optional[str] = Query(None),
    success: Optional[bool] = Query(None, description="true=exitosos, false=fallidos"),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=1000),
    admin=Depends(get_admin),
):
    """Intentos de inicio de sesión con país (geolocalización por IP) y motivo de fallo."""
    return queries.login_attempts_data(user_id, success, days, limit)


@app.get(f"{API_PREFIX}/storage", response_model=schemas.StorageStats, tags=["panel"])
def get_storage(
    group_id: Optional[str] = Query(None),
    admin=Depends(get_admin),
):
    """Estadísticas de almacenamiento: contraseñas, bóvedas, secretos, compartidos y grupos."""
    return queries.storage_data(group_id)


@app.get(f"{API_PREFIX}/obsolete", response_model=List[schemas.ObsoleteEntry], tags=["panel"])
def get_obsolete(
    kind: str = Query("all", pattern="^(passwords|secrets|all)$"),
    owner: Optional[str] = Query(None, description="Filtrar por email o nombre del propietario"),
    limit: int = Query(200, ge=1, le=1000),
    admin=Depends(get_admin),
):
    """Registros obsoletos (contraseñas y secretos de origen desconocido)."""
    return queries.obsolete_data(kind, owner, limit)
