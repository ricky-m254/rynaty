import hashlib
import os
import warnings
from datetime import timedelta
from pathlib import Path

# Suppress harmless pkg_resources deprecation warning from simplejwt
warnings.filterwarnings(
    'ignore',
    message='pkg_resources is deprecated as an API',
    category=UserWarning,
)

from corsheaders.defaults import default_headers
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# ==========================================
# PATH CONFIGURATION
# ==========================================
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


# ==========================================
# CORE SETTINGS
# ==========================================
def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name, "")
    if not value.strip():
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _jwt_signing_key(secret_key: str) -> str:
    configured_key = os.getenv("DJANGO_JWT_SECRET_KEY", "").strip()
    candidate = configured_key or secret_key
    candidate_bytes = candidate.encode("utf-8")
    if len(candidate_bytes) >= 32:
        return candidate
    # Short development secrets are normalized so JWT signing stays warning-free.
    return hashlib.sha256(candidate_bytes).hexdigest()


def _env_str(
    name: str,
    default: str | None = None,
    *,
    required: bool = False,
    allow_blank: bool = False,
) -> str:
    value = os.getenv(name, default)
    if value is None:
        if required:
            raise ImproperlyConfigured(f"Missing required environment variable: {name}")
        return ""
    value = str(value).strip()
    if not value and required and not allow_blank:
        raise ImproperlyConfigured(f"Environment variable {name} cannot be blank.")
    return value


def _env_int(
    name: str,
    default: int | None = None,
    *,
    required: bool = False,
    min_value: int | None = None,
) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        if default is not None:
            value = default
        elif required:
            raise ImproperlyConfigured(f"Missing required environment variable: {name}")
        else:
            return 0
    else:
        try:
            value = int(str(raw).strip())
        except ValueError as exc:
            raise ImproperlyConfigured(
                f"Environment variable {name} must be an integer."
            ) from exc
    if min_value is not None and value < min_value:
        raise ImproperlyConfigured(
            f"Environment variable {name} must be >= {min_value}."
        )
    return value


def _assert_not_placeholder(name: str, value: str, placeholders: set[str]) -> None:
    normalized = str(value or "").strip().lower()
    if normalized in placeholders:
        raise ImproperlyConfigured(
            f"Environment variable {name} uses a placeholder/weak value. Set a secure production value."
        )


DEBUG = _env_bool("DJANGO_DEBUG", default=False)
ALLOW_INSECURE_DEFAULTS = _env_bool("DJANGO_ALLOW_INSECURE_DEFAULTS", default=False)
STRICT_PRODUCTION_MODE = not DEBUG and not ALLOW_INSECURE_DEFAULTS
DJANGO_TENANT_SECRET_KEYS = _env_list("DJANGO_TENANT_SECRET_KEYS", [])
RENDER_EXTERNAL_HOSTNAME = _env_str("RENDER_EXTERNAL_HOSTNAME", default="")
RENDER_EXTERNAL_HOST = RENDER_EXTERNAL_HOSTNAME.split(":")[0].strip().lower()

if DEBUG and ALLOW_INSECURE_DEFAULTS:
    SECRET_KEY = _env_str(
        "DJANGO_SECRET_KEY",
        default="dev-only-insecure-key-change-before-production",
    )
else:
    SECRET_KEY = _env_str("DJANGO_SECRET_KEY", required=True)

ALLOWED_HOSTS = _env_list(
    "DJANGO_ALLOWED_HOSTS",
    (
        ["127.0.0.1", "localhost", "demo.localhost", "oxford.localhost"]
        if DEBUG and ALLOW_INSECURE_DEFAULTS
        else ([RENDER_EXTERNAL_HOST] if RENDER_EXTERNAL_HOST else [])
    ),
)

# Auto-include Replit proxy domains so the dev/prod previews always work
_replit_domains = os.environ.get("REPLIT_DOMAINS", "")
for _d in _replit_domains.split(","):
    _d = _d.strip()
    if _d and _d not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_d)

if RENDER_EXTERNAL_HOST and RENDER_EXTERNAL_HOST not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOST)

# Also allow any custom/production domains listed in EXTRA_TENANT_DOMAINS so
# that a single env-var registers the hostname in both the tenant Domain table
# (handled by start.sh) and Django's ALLOWED_HOSTS check.
_extra_domains = os.environ.get("EXTRA_TENANT_DOMAINS", "")
for _d in _extra_domains.split(","):
    _d = _d.strip()
    if _d and _d not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_d)

# Hardcoded production domains — always allowed regardless of env vars.
for _d in ["rynatyschool.app", "www.rynatyschool.app", "olom.rynatyschool.app"]:
    if _d not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_d)

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be configured.")


# ==========================================
# INSTALLED APPS
# ==========================================
SHARED_APPS = [
    "corsheaders",
    "django_tenants",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "clients",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admin",
]

TENANT_APPS = [
    "school",
    "admissions",
    "academics",
    "library",
    "parent_portal",
    "hr",
    "staff_mgmt",
    "assets",
    "communication",
    "reporting",
    "clockin",
    "timetable",
    # New modules
    "transport",
    "visitor_mgmt",
    "examinations",
    "alumni",
    "hostel",
    "ptm",
    "sports",
    "cafeteria",
    "curriculum",
    "maintenance",
    "elearning",
    "analytics",
    "rest_framework_simplejwt.token_blacklist",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admin",
]

INSTALLED_APPS = list(set(SHARED_APPS) | set(TENANT_APPS))


# ==========================================
# MIDDLEWARE (CRITICAL ORDER)
# ==========================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "clients.middleware.HealthCheckMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django_tenants.middleware.main.TenantMainMiddleware",
    "clients.middleware.TenantContextGuardMiddleware",
    "clients.middleware.PlatformPublicSchemaMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "domains.auth.infrastructure.has_permission_middleware.HasPermissionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ==========================================
# DATABASE
# ==========================================
_DATABASE_URL = os.environ.get("DATABASE_URL", "")
if _DATABASE_URL:
    from urllib.parse import urlparse as _urlparse
    _parsed_db = _urlparse(_DATABASE_URL)
    DATABASES = {
        "default": {
            "ENGINE": "django_tenants.postgresql_backend",
            "NAME": _parsed_db.path.lstrip("/"),
            "USER": _parsed_db.username or "",
            "PASSWORD": _parsed_db.password or "",
            "HOST": _parsed_db.hostname or "localhost",
            "PORT": str(_parsed_db.port or 5432),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django_tenants.postgresql_backend",
            "NAME": _env_str(
                "POSTGRES_DB",
                default=os.environ.get("PGDATABASE", "sms_school_db" if DEBUG and ALLOW_INSECURE_DEFAULTS else None),
                required=not (DEBUG and ALLOW_INSECURE_DEFAULTS),
            ),
            "USER": _env_str(
                "POSTGRES_USER",
                default=os.environ.get("PGUSER", "postgres" if DEBUG and ALLOW_INSECURE_DEFAULTS else None),
                required=not (DEBUG and ALLOW_INSECURE_DEFAULTS),
            ),
            "PASSWORD": _env_str(
                "POSTGRES_PASSWORD",
                default=os.environ.get("PGPASSWORD", "postgres" if DEBUG and ALLOW_INSECURE_DEFAULTS else None),
                required=not (DEBUG and ALLOW_INSECURE_DEFAULTS),
                allow_blank=DEBUG and ALLOW_INSECURE_DEFAULTS,
            ),
            "HOST": _env_str(
                "POSTGRES_HOST",
                default=os.environ.get("PGHOST", "localhost" if DEBUG and ALLOW_INSECURE_DEFAULTS else None),
                required=not (DEBUG and ALLOW_INSECURE_DEFAULTS),
            ),
            "PORT": _env_str(
                "POSTGRES_PORT",
                default=os.environ.get("PGPORT", "5432" if DEBUG and ALLOW_INSECURE_DEFAULTS else None),
                required=not (DEBUG and ALLOW_INSECURE_DEFAULTS),
            ),
        }
    }


# ==========================================
# TENANCY SETTINGS
# ==========================================
TENANT_MODEL = "clients.Tenant"
TENANT_DOMAIN_MODEL = "clients.Domain"

PUBLIC_SCHEMA_NAME = "public"
PUBLIC_SCHEMA_URLCONF = "config.public_urls"

# Fall back to public schema (and PUBLIC_SCHEMA_URLCONF) when the request
# host is not registered as a tenant domain.  This allows the deployed
# .replit.app URL (which is always registered as the public tenant) to
# work even if the build script's domain-registration step didn't run.
# Our TenantContextGuardMiddleware + _tenant_aware_login_view then handle
# tenant switching via the X-Tenant-ID header.
SHOW_PUBLIC_IF_NO_TENANT_FOUND = True

TENANT_HEADER_NAME = _env_str("TENANT_HEADER_NAME", default="X-Tenant-ID")
TENANT_HEADERS = [TENANT_HEADER_NAME]
TENANT_REQUIRE_HEADER = _env_bool("TENANT_REQUIRE_HEADER", default=False)
TENANT_ENFORCE_HEADER_MATCH = _env_bool("TENANT_ENFORCE_HEADER_MATCH", default=True)
TENANT_ENFORCE_HOST_MATCH = _env_bool("TENANT_ENFORCE_HOST_MATCH", default=True)
TENANT_GUARD_API_PREFIX = _env_str("TENANT_GUARD_API_PREFIX", default="/api/")

DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)

# Module focus lock: optional narrowing for targeted hardening windows.
# Default is disabled so all modules remain available unless explicitly locked.
MODULE_FOCUS_LOCK = _env_bool("MODULE_FOCUS_LOCK", default=False)
MODULE_FOCUS_KEYS = [
    key.upper()
    for key in _env_list(
        "MODULE_FOCUS_KEYS",
        ["FINANCE", "STUDENTS", "ACADEMICS", "CORE"],
    )
]


# ==========================================
# REST FRAMEWORK & AUTH
# ==========================================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "clients.authentication.TenantAwareJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DATETIME_FORMAT": "%Y-%m-%d %H:%M:%S",
    # Spec §9.1 — standardised error response format across all API endpoints
    "EXCEPTION_HANDLER": "clients.exceptions.platform_exception_handler",
    # Rate limiting — spec §10.1: 5/5min login, 100/min general
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/minute",   # unauthenticated (login attempts, public endpoints)
        "user": "300/minute",  # authenticated users (generous for school operations)
        "platform_login": "5/minute",  # spec: 5 login attempts per 5 min
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "SIGNING_KEY": _jwt_signing_key(SECRET_KEY),
}


# ==========================================
# CORS CONFIGURATION (FRONTEND INTEGRATION)
# ==========================================
CORS_ALLOWED_ORIGINS = [
    *(
        _env_list(
            "CORS_ALLOWED_ORIGINS",
            (
                [
                    "http://localhost:3000",
                    "http://127.0.0.1:3000",
                    "http://demo.localhost:3000",
                    "http://demo.localhost:8000",
                ]
                if DEBUG and ALLOW_INSECURE_DEFAULTS
                else []
            ),
        )
    )
]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = list(default_headers) + [TENANT_HEADER_NAME.lower()]

CSRF_TRUSTED_ORIGINS = _env_list(
    "CSRF_TRUSTED_ORIGINS",
    (
        [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://demo.localhost:3000",
            "http://localhost:5000",
            "http://127.0.0.1:5000",
        ]
        if DEBUG and ALLOW_INSECURE_DEFAULTS
        else []
    ),
)

# Auto-include Replit proxy domains in CORS and CSRF
for _d in _replit_domains.split(","):
    _d = _d.strip()
    if _d:
        for _scheme in ("https://", "http://"):
            _origin = f"{_scheme}{_d}"
            if _origin not in CORS_ALLOWED_ORIGINS:
                CORS_ALLOWED_ORIGINS.append(_origin)
            if _origin not in CSRF_TRUSTED_ORIGINS:
                CSRF_TRUSTED_ORIGINS.append(_origin)

if RENDER_EXTERNAL_HOST:
    for _scheme in (("https://", "http://") if DEBUG else ("https://",)):
        _origin = f"{_scheme}{RENDER_EXTERNAL_HOST}"
        if _origin not in CORS_ALLOWED_ORIGINS:
            CORS_ALLOWED_ORIGINS.append(_origin)
        if _origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_origin)

# Also trust any custom/production domains from EXTRA_TENANT_DOMAINS
for _d in _extra_domains.split(","):
    _d = _d.strip()
    if _d:
        _origin = f"https://{_d}"
        if _origin not in CORS_ALLOWED_ORIGINS:
            CORS_ALLOWED_ORIGINS.append(_origin)
        if _origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_origin)

# Hardcoded production domains — always trusted for CORS and CSRF.
for _d in ["rynatyschool.app", "www.rynatyschool.app", "olom.rynatyschool.app"]:
    _origin = f"https://{_d}"
    if _origin not in CORS_ALLOWED_ORIGINS:
        CORS_ALLOWED_ORIGINS.append(_origin)
    if _origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_origin)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = _env_bool("DJANGO_SECURE_SSL_REDIRECT", default=not DEBUG)
SESSION_COOKIE_SAMESITE = _env_str("DJANGO_SESSION_COOKIE_SAMESITE", default="Lax")
CSRF_COOKIE_SAMESITE = _env_str("DJANGO_CSRF_COOKIE_SAMESITE", default="Lax")
SECURE_HSTS_SECONDS = _env_int(
    "DJANGO_SECURE_HSTS_SECONDS",
    default=31536000 if STRICT_PRODUCTION_MODE else 0,
    min_value=0,
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=STRICT_PRODUCTION_MODE,
)
SECURE_HSTS_PRELOAD = _env_bool(
    "DJANGO_SECURE_HSTS_PRELOAD",
    default=STRICT_PRODUCTION_MODE,
)
SECURE_REFERRER_POLICY = _env_str(
    "DJANGO_SECURE_REFERRER_POLICY",
    default="strict-origin-when-cross-origin",
)


# ==========================================
# STATIC FILES
# ==========================================
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Whitenoise also serves the React production build from this directory
WHITENOISE_ROOT = BASE_DIR / "frontend_build"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ==========================================
# COMMUNICATION PROVIDER PLACEHOLDERS
# ==========================================
COMMUNICATION_SMS_API_KEY = os.getenv("COMMUNICATION_SMS_API_KEY", "")
COMMUNICATION_WHATSAPP_API_KEY = os.getenv("COMMUNICATION_WHATSAPP_API_KEY", "")
COMMUNICATION_PUSH_SERVER_KEY = os.getenv("COMMUNICATION_PUSH_SERVER_KEY", "")
COMMUNICATION_WEBHOOK_TOKEN = os.getenv("COMMUNICATION_WEBHOOK_TOKEN", "")
COMMUNICATION_WEBHOOK_SHARED_SECRET = os.getenv("COMMUNICATION_WEBHOOK_SHARED_SECRET", "")
COMMUNICATION_WEBHOOK_REQUIRE_TIMESTAMP = os.getenv(
    "COMMUNICATION_WEBHOOK_REQUIRE_TIMESTAMP",
    "false" if DEBUG else "true",
).lower() == "true"
COMMUNICATION_WEBHOOK_MAX_AGE_SECONDS = int(os.getenv("COMMUNICATION_WEBHOOK_MAX_AGE_SECONDS", "300"))
COMMUNICATION_WEBHOOK_STRICT_MODE = os.getenv(
    "COMMUNICATION_WEBHOOK_STRICT_MODE",
    "false" if DEBUG else "true",
).lower() == "true"


# ==========================================
# FINANCE GATEWAY PLACEHOLDERS
# ==========================================
FINANCE_PAYMENT_GATEWAY_PROVIDER = os.getenv("FINANCE_PAYMENT_GATEWAY_PROVIDER", "placeholder")
FINANCE_PAYMENT_GATEWAY_API_KEY = os.getenv("FINANCE_PAYMENT_GATEWAY_API_KEY", "")
FINANCE_WEBHOOK_TOKEN = os.getenv("FINANCE_WEBHOOK_TOKEN", "")
FINANCE_WEBHOOK_SHARED_SECRET = os.getenv("FINANCE_WEBHOOK_SHARED_SECRET", "")
FINANCE_WEBHOOK_STRICT_MODE = os.getenv(
    "FINANCE_WEBHOOK_STRICT_MODE",
    "false" if DEBUG else "true",
).lower() == "true"

# ==========================================
# DEPLOYMENT PIPELINE HOOKS
# ==========================================
DEPLOYMENT_CALLBACK_TOKEN = os.getenv("DEPLOYMENT_CALLBACK_TOKEN", "")
DEPLOYMENT_TRIGGER_HOOK_URL = os.getenv("DEPLOYMENT_TRIGGER_HOOK_URL", "")
DEPLOYMENT_ROLLBACK_HOOK_URL = os.getenv("DEPLOYMENT_ROLLBACK_HOOK_URL", "")
DEPLOYMENT_HOOK_TIMEOUT_SECONDS = int(os.getenv("DEPLOYMENT_HOOK_TIMEOUT_SECONDS", "6"))

# ==========================================
# BACKUP ENGINE ORCHESTRATION
# ==========================================
BACKUP_ENGINE_MODE = os.getenv("BACKUP_ENGINE_MODE", "mock")
BACKUP_ARTIFACT_DIR = os.getenv("BACKUP_ARTIFACT_DIR", str(BASE_DIR / "var" / "backups"))
BACKUP_ENGINE_TIMEOUT_SECONDS = int(os.getenv("BACKUP_ENGINE_TIMEOUT_SECONDS", "120"))


# ==========================================
# PARENT PORTAL LINKAGE
# ==========================================
PARENT_PORTAL_ALLOW_GUARDIAN_FALLBACK = os.getenv(
    "PARENT_PORTAL_ALLOW_GUARDIAN_FALLBACK",
    "true" if DEBUG else "false",
).lower() == "true"


# ==========================================
# PLATFORM (SUPER TENANT ADMIN)
# ==========================================
_replit_first_domain = _replit_domains.split(",")[0].strip() if _replit_domains else ""
# Prefer the custom production domain (EXTRA_TENANT_DOMAINS) over the Replit
# auto-assigned domain so that new tenants get e.g. <name>.rynatyschool.app
# rather than <name>.some-hash.replit.app.
# Falls back to the hardcoded production domain as a last resort before the
# Replit auto-domain, so the env var EXTRA_TENANT_DOMAINS is not strictly required.
_extra_first_domain = _extra_domains.split(",")[0].strip() if _extra_domains else ""
_hardcoded_prod_domain = "rynatyschool.app"
_platform_base_domain_default = (
    "localhost" if DEBUG and ALLOW_INSECURE_DEFAULTS
    else (_extra_first_domain or _hardcoded_prod_domain)
)
PLATFORM_DEFAULT_BASE_DOMAIN = _env_str(
    "PLATFORM_DEFAULT_BASE_DOMAIN",
    default=_platform_base_domain_default,
    required=False,
)
PLATFORM_DEFAULT_TRIAL_DAYS = _env_int(
    "PLATFORM_DEFAULT_TRIAL_DAYS",
    default=14,
    min_value=1,
)
PLATFORM_BILLING_GRACE_DAYS = _env_int(
    "PLATFORM_BILLING_GRACE_DAYS",
    default=7,
    min_value=0,
)
PLATFORM_MAINTENANCE_NOTIFY_CHANNELS = _env_str("PLATFORM_MAINTENANCE_NOTIFY_CHANNELS", default="IN_APP,EMAIL")


# ==========================================
# PRODUCTION SECRET HYGIENE GUARDS
# ==========================================
if STRICT_PRODUCTION_MODE:
    _assert_not_placeholder(
        "DJANGO_SECRET_KEY",
        SECRET_KEY,
        {
            "",
            "changeme",
            "change-me",
            "change-me-before-production",
            "dev-only-insecure-key-change-before-production",
            "dev-local-secret-key-change-me",
            "replace-with-strong-random-secret",
        },
    )
    _assert_not_placeholder(
        "POSTGRES_PASSWORD",
        DATABASES["default"]["PASSWORD"],
        {
            "",
            "postgres",
            "password",
            "changeme",
            "change-me",
            "replace-with-strong-db-password",
        },
    )
    _assert_not_placeholder(
        "FINANCE_WEBHOOK_SHARED_SECRET",
        FINANCE_WEBHOOK_SHARED_SECRET,
        {"", "changeme", "change-me", "replace"},
    )
    _assert_not_placeholder(
        "DEPLOYMENT_CALLBACK_TOKEN",
        DEPLOYMENT_CALLBACK_TOKEN,
        {"", "changeme", "change-me", "replace"},
    )
    _assert_not_placeholder(
        "COMMUNICATION_WEBHOOK_SHARED_SECRET",
        COMMUNICATION_WEBHOOK_SHARED_SECRET,
        {"", "changeme", "change-me", "replace"},
    )
    _assert_not_placeholder(
        "PLATFORM_DEFAULT_BASE_DOMAIN",
        PLATFORM_DEFAULT_BASE_DOMAIN,
        {"localhost", "127.0.0.1", "example.com", "changeme", "change-me"},
    )
    _assert_not_placeholder(
        "FINANCE_PAYMENT_GATEWAY_PROVIDER",
        FINANCE_PAYMENT_GATEWAY_PROVIDER,
        {"", "placeholder", "mock", "changeme", "change-me", "replace"},
    )
    _assert_not_placeholder(
        "BACKUP_ENGINE_MODE",
        BACKUP_ENGINE_MODE,
        {"", "mock", "changeme", "change-me", "replace"},
    )
    if not SECURE_SSL_REDIRECT:
        raise ImproperlyConfigured(
            "DJANGO_SECURE_SSL_REDIRECT must be true in strict production mode."
        )
    if SECURE_HSTS_SECONDS <= 0:
        raise ImproperlyConfigured(
            "DJANGO_SECURE_HSTS_SECONDS must be > 0 in strict production mode."
        )
    if not CORS_ALLOWED_ORIGINS:
        raise ImproperlyConfigured(
            "CORS_ALLOWED_ORIGINS must be configured in strict production mode."
        )
    if not CSRF_TRUSTED_ORIGINS:
        raise ImproperlyConfigured(
            "CSRF_TRUSTED_ORIGINS must be configured in strict production mode."
        )
    if not all(origin.startswith("https://") for origin in CORS_ALLOWED_ORIGINS):
        raise ImproperlyConfigured(
            "CORS_ALLOWED_ORIGINS must use HTTPS in strict production mode."
        )
    if not all(origin.startswith("https://") for origin in CSRF_TRUSTED_ORIGINS):
        raise ImproperlyConfigured(
            "CSRF_TRUSTED_ORIGINS must use HTTPS in strict production mode."
        )
