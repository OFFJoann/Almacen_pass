# TICO BOX · Enterprise Password Manager (EPM)

Gestor de contraseñas y secretos empresarial para equipos. Permite a una
organización almacenar credenciales, secretos y TOTP de forma cifrada, con
control de acceso por roles, auditoría, MFA, políticas por grupo y un módulo de
**licenciamiento** que limita el número de usuarios activos según una licencia
validada contra un servicio externo.

> Stack: **Django 5** (web) · **FastAPI** (servicios auxiliares) · **PostgreSQL**
> · **Redis** · **Celery** · cifrado **AES-GCM + Argon2id** en reposo.

---

## 1. Características principales

- **Bóveda de contraseñas**: usuario, contraseña, URL, notas y secreto TOTP por
  entrada, cifrados en reposo (AES-GCM con derivación Argon2id por campo).
- **Secretos**: almacén de secretos/notas sensibles (targetas, API keys, etc.).
- **TOTP / MFA**: autenticación de dos factores (django-otp + django-mfa2).
- **Roles**: `superadmin`, `administrador` (puede gestionar usuarios) y
  `miembro` estándar.
- **Grupos con políticas**: longitud mínima de contraseña, retención, sesión y
  políticas de exportación por grupo.
- **Auditoría**: middleware de auditoría + `django-simple-history`; registro de
  acciones, IP y resultado.
- **Protección anti-intrusión**: `django-axes` (bloqueo por fuerza bruta),
  `django-csp`, rate limiting y cabeceras de seguridad.
- **Filtraciones (dark web / HIBP)**: comprobación de contraseñas comprometidas.
- **Onboarding**: tour de bienvenida para nuevos usuarios.
- **Notificaciones** y **mailer** (SMTP configurable).
- **SSO**: aprovisionamiento just-in-time de usuarios vía SSO.
- **API de reportes** (FastAPI aparte): métricas de riesgo, usuarios, grupos,
  auditoría, intentos de login, almacenamiento y registros obsoletos.
- **Licenciamiento** (FastAPI aparte): valida `empresa` + `licencia` y limita la
  creación de usuarios activos en la instancia.

---

## 2. Arquitectura

El producto se compone de **tres procesos independientes** más una extensión de
navegador, que comparten la misma base de datos PostgreSQL (los servicios
FastAPI usan `django.setup()` para leer el ORM).

```
┌──────────────────────────────────────────────────────────────┐
│  Navegador                                                   │
│  ├─ App web (Django)  ── HTMX / Bootstrap 5 / Crispy          │
│  └─ Extensión (Manifest V3: popup / options / content)        │
└───────────────┬───────────────────────────┬─────────────────┘
                │ HTTP                       │ HTTP (ApiToken)
                ▼                            ▼
        ┌───────────────┐           ┌──────────────────────┐
        │ Django EPM     │           │ Reports API (FastAPI)│  :8001
        │  - web/views   │           │ /api/v1/admin/*       │
        │  - api_tokens  │           └──────────┬───────────┘
        │  - licensing   │                      │ consulta
        └───────┬───────┘                      │
                │                              │
       ┌────────┴─────────┐         ┌──────────┴───────────┐
       │ PostgreSQL (DB)  │◄────────┤  (mismo ORM Django)  │
       └────────┬─────────┘         └──────────────────────┘
                │
       ┌────────┴─────────┐
       │ Redis (cache/    │  ◄── Celery worker + beat
       │ sesiones)        │
       └──────────────────┘

  Licencias (separado, del proveedor):
   Panel Django ──POST /licencias──► License API (FastAPI) :8002
                                    (sin auth, lee licenses.json)
```

### Componentes

| Componente | Tecnología | Puertos | Auth |
|---|---|---|---|
| App web EPM | Django 5 + DRF + HTMX | 8000 (gunicorn) | Sesión / MFA |
| Reports API | FastAPI | 8001 | `ApiToken` (Bearer/`?token=`) |
| License API | FastAPI | 8002 | Ninguna (proveedor) |
| PostgreSQL | — | 5432 | Usuario/contraseña |
| Redis | — | 6379 | — |
| Celery | worker + beat | — | — |
| Extensión navegador | MV3 (JS) | — | Sesión del sitio |

---

## 3. Estructura del repositorio

```
enterprise_password_manager/
├── apps/                      # Aplicaciones Django locales
│   ├── authentication/        # Login, MFA, cabeceras de seguridad, sesión
│   ├── users/                 # Usuarios, roles, límite de licencia (User.save)
│   ├── passwords/             # Bóveda, cifrado (AES-GCM+Argon2id), TOTP, onboarding
│   ├── secrets/               # Almacén de secretos cifrados
│   ├── audit/                 # Auditoría y simple_history
│   ├── notifications/         # Notificaciones in-app
│   ├── sso/                   # SSO / aprovisionamiento JIT
│   ├── admin_dashboard/       # Panel admin, tokens API, documentación propia
│   ├── api_tokens/            # Modelo ApiToken (auth Reports API)
│   ├── licensing/             # Licencia por instancia + consumo de License API
│   └── mailer/                # Configuración SMTP
├── config/                    # settings (base/dev/prod), urls, wsgi
├── reports_api/               # Servicio FastAPI de reportes (separado)
├── license_api/               # Servicio FastAPI de licencias (separado)
├── browser_extension/         # Extensión Manifest V3 (popup/options/content)
├── docker/                    # entrypoint.sh + nginx.conf
├── static/  templates/  logs/
└── requirements.txt
```

---

## 4. Roles y permisos

- **superadmin**: control total, incluye gestión de licencia y configuración del
  proveedor de correo.
- **administrador** (`can_manage_users()`): gestiona usuarios, grupos y ve el
  panel de administración / Tokens de API.
- **miembro**: usa su bóveda y secretos; solo ve lo suyo.

---

## 5. Seguridad y cifrado

- **Cifrado en reposo**: cada campo sensible (contraseña, usuario, notas, TOTP,
  secretos, contraseña SMTP) se guarda como `ciphertext` + `nonce` + `salt`.
  Algoritmo: **AES-GCM** con clave derivada por **Argon2id** (librería
  `cryptography`). El descifrado usa la clave maestra derivada del `SECRET_KEY`.
- **MFA**: TOTP obligatorio para administradores (contacto de emergencia).
- **Anti-fuerza-bruta**: `django-axes` bloquea tras 5 fallos (cool-off 30 min).
- **Cabeceras**: CSP, HSTS, `X-Frame-Options: DENY`, cookies `HttpOnly`/`Secure`,
  `SameSite=Lax`, sesión expira al cerrar navegador.
- **Auditoría**: middleware registra acciones, IP y resultado; `simple_history`
  versiona cambios.
- **Rate limiting** y CSRF habilitados.

---

## 6. Puesta en marcha (desarrollo)

### Requisitos
- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- (opcional) Celery + broker Redis

### Instalación

```powershell
cd enterprise_password_manager
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### Configuración (`.env` en la raíz)

```ini
SECRET_KEY=tu-clave-secreta-larga
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_NAME=epm_db
DB_USER=epm_user
DB_PASSWORD=epm_password
DB_HOST=localhost
DB_PORT=5432
REDIS_URL=redis://localhost:6379/0
API_REPORTS_BASE_URL=http://127.0.0.1:8001
LICENSE_API_URL=http://127.0.0.1:8002
```

### Migraciones y arranque

```powershell
$env:DJANGO_SETTINGS_MODULE='config.settings.development'
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 8000
```

Accede a `http://127.0.0.1:8000` e inicia sesión.

---

## 7. Servicios FastAPI auxiliares

### 7.1 Reports API (`reports_api/`, puerto 8001)

Servicio **separado** que expone métricas agregadas del panel para generar
informes automatizados. Se autentica con un **ApiToken** generado en
*Panel → Tokens de API* (sección admin), enviado como
`Authorization: Bearer <token>` o `?token=<token>`. El token debe estar activo,
no caducado y pertenecer a un usuario administrador.

Endpoints (prefijo `/api/v1/admin`):

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Meta |
| GET | `/overview` | Resumen general (usuarios, riesgo, filtraciones) |
| GET | `/users` | Listado de usuarios con riesgo individual |
| GET | `/users/{user_id}` | Detalle de usuario |
| GET | `/groups` | Grupos y sus políticas |
| GET | `/risk` | Riesgo agregado |
| GET | `/darkweb` | Contraseñas en filtraciones |
| GET | `/audit` | Registro de auditoría |
| GET | `/login-attempts` | Intentos de login (geo-IP) |
| GET | `/storage` | Estadísticas de almacenamiento |
| GET | `/obsolete` | Registros obsoletos |

Documentación interactiva en `/docs` (Swagger). Para ejecutarlo:

```powershell
cd reports_api
pip install fastapi uvicorn[standard]
uvicorn main:app --port 8001
```

### 7.2 License API (`license_api/`, puerto 8002)

Servicio **separado del proveedor** (tú lo despliegas donde quieras). Valida
licencias contra un JSON plano editable, **sin autenticación**.

- `POST /licencias` → body `{ "empresa": "...", "licencia": "..." }`
  - Respuesta válida: `{ "valid": true, "max_users": N, "expires_at": "ISO", "installation_id": "", "notes": "" }`
  - Respuesta inválida: `{ "valid": false, "error": "..." }`
- `GET /licencias/{empresa}` → lista de licencias de una empresa (sin clave).

`licenses.json` (ejemplo):

```json
[
  {
    "empresa": "Acme SAS",
    "licencia": "LIC-ACME-7F3A9C",
    "max_users": 25,
    "expires_at": "2026-12-31T23:59:59",
    "active": true,
    "notes": "Plan anual"
  }
]
```

Ejecución:

```powershell
cd license_api
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --port 8002
```

---

## 8. Módulo de licenciamiento (caso de uso)

**Modelo de negocio:** licencia **por instancia**. Cada instalación del producto
es un cliente; la licencia fija un **número máximo de usuarios activos**. Solo
cuentan los usuarios con `is_active=True`. El tenant **solo activa** la licencia;
el proveedor la genera y administra en su propio servicio.

**Flujo:**

1. **Proveedor**: mantiene `licenses.json` (o su propia fuente) con
   `empresa`, `licencia`, `max_users`, `expires_at`, `active`. Despliega la
   License API accesible por la instancia del cliente.
2. **Tenant (superadmin)**: en *Panel → Licencia* introduce **Empresa**,
   **URL de la API de licencias** y **Clave**; pulsa *Activar licencia*.
3. El panel hace `POST {URL}/licencias` con `{empresa, licencia}`.
   - Válida → guarda `max_users`, `expires_at`, `is_valid=True`.
   - Inválida → `is_valid=False` + error; la creación de usuarios queda bloqueada.
4. **Uso diario**: cada alta de usuario (admin, SSO JIT) o activación de un
   usuario inactivo se bloquea si `activos >= max_users`. Si `expires_at`
   pasó, el panel lo marca localmente como caducado y bloquea la creación.
5. **Revalidar**: si el proveedor cambia la licencia (revoca, amplía, renueva),
   el tenant pulsa *Revalidar* para reconsultar la API.

**Casos borde:**
- Sin licencia configurada → se permite crear (setup inicial).
- Licencia configurada pero inválida/caducada → se bloquea crear usuarios
  hasta activar una válida.
- El tenant no puede firmar ni generar licencias (no hay secreto en su instancia).

---

## 9. Caso de uso típico (end-to-end)

1. El proveedor entrega a la empresa cliente la instancia Django + la URL de su
   License API.
2. La empresa instala, crea el superadmin y activa su licencia (empresa + clave).
3. El superadmin crea grupos, define políticas (longitud, retención, exportación)
   e invita a administradores y miembros hasta el límite de la licencia.
4. Los miembros guardan contraseñas y secretos en su bóveda cifrada; habilitan
   MFA; el sistema alerta de contraseñas en filtraciones (HIBP).
5. El administrador consulta el panel de riesgo y, vía Reports API, genera
   informes para cumplimiento/auditoría.
6. Cuando la empresa necesita más usuarios, el proveedor amplía `max_users` en
   su License API; el cliente pulsa *Revalidar*.

---

## 10. Variables de entorno clave

| Variable | Descripción | Defecto |
|---|---|---|
| `SECRET_KEY` | Clave maestra (deriva claves de cifrado) | dev inseguro |
| `DEBUG` | Modo debug | `False` |
| `ALLOWED_HOSTS` | Hosts permitidos | `localhost,127.0.0.1` |
| `DB_*` | Credenciales PostgreSQL | `epm_*` |
| `REDIS_URL` | URL de Redis (cache/sesiones/Celery) | `redis://localhost:6379/0` |
| `API_REPORTS_BASE_URL` | Base de la Reports API | `http://127.0.0.1:8001` |
| `LICENSE_API_URL` | Base de la License API (defecto si el panel no la fija) | `http://127.0.0.1:8002` |
| `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` | Cookies seguras (prod) | `False` |
| `SECURE_SSL_REDIRECT` | Redirigir a HTTPS | `False` |
| `LOG_LEVEL` | Nivel de log | `INFO` |

---

## 11. Despliegue

Se incluyen `docker/entrypoint.sh` y `docker/nginx.conf` como referencia para
servir la app con gunicorn tras nginx (WhiteNoise para estáticos). Los servicios
FastAPI (Reports y License) se ejecutan como procesos independientes apuntando a
la misma base de datos (Reports) o a su propio JSON (License).

Recomendaciones de producción:
- `DEBUG=False`, `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`,
  `SECURE_SSL_REDIRECT=True`.
- `SECRET_KEY` fuerte y única por instancia.
- PostgreSQL y Redis en red privada; Celery con broker Redis.
- La License API del proveedor debe exponerse solo a las instancias autorizadas.

---

## 12. Extensión de navegador

Carpeta `browser_extension/` (Manifest V3) con `popup`, `options`, `content`,
`lib` e `icons`. Permite autocompletar credenciales desde la bóveda del usuario
usando la sesión del sitio. No almacena secretos por sí misma.
