$ErrorActionPreference = "Stop"

$repo = "C:\Users\emuri\OneDrive\Desktop\Sms-Deployment"
$backend = Join-Path $repo "sms-backend"
$python = Join-Path $repo ".venv\Scripts\python.exe"
$log = Join-Path $repo "artifacts\local_django.log"
$err = Join-Path $repo "artifacts\local_django.err.log"

Set-Location $backend

$env:PYTHONPATH = Join-Path $backend "artifacts\test_shims"
$env:DJANGO_DEBUG = "true"
$env:DJANGO_ALLOW_INSECURE_DEFAULTS = "true"
$env:DJANGO_SECRET_KEY = "change-me-before-production"
$env:DJANGO_ALLOWED_HOSTS = "127.0.0.1,localhost,demo.localhost"
$env:DJANGO_SECURE_SSL_REDIRECT = "false"
$env:DJANGO_SESSION_COOKIE_SAMESITE = "Lax"
$env:DJANGO_CSRF_COOKIE_SAMESITE = "Lax"
$env:DJANGO_SECURE_HSTS_SECONDS = "0"
$env:DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS = "false"
$env:DJANGO_SECURE_HSTS_PRELOAD = "false"
$env:DJANGO_SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
$env:TENANT_HEADER_NAME = "X-Tenant-ID"
$env:TENANT_REQUIRE_HEADER = "false"
$env:TENANT_ENFORCE_HEADER_MATCH = "true"
$env:TENANT_ENFORCE_HOST_MATCH = "true"
$env:TENANT_GUARD_API_PREFIX = "/api/"
$env:DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:55432/test_sms_school_db"
$env:BOOTSTRAP_DEMO_DATA = "true"
$env:DEMO_SCHEMA_NAME = "demo_school"
$env:DEMO_TENANT_DOMAIN = "demo.localhost"
$env:DEMO_SCHOOL_NAME = "RynatySchool Demo"
$env:DEMO_ADMIN_USER = "Riqs#."
$env:DEMO_ADMIN_PASS = "Ointment.54.#"
$env:DEMO_ADMIN_EMAIL = "admin@demo.school"
$env:PYTHONUNBUFFERED = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

if (Test-Path $log) {
    Remove-Item -LiteralPath $log -Force
}
if (Test-Path $err) {
    Remove-Item -LiteralPath $err -Force
}

& $python manage.py runserver 127.0.0.1:8080 --noreload 1>> $log 2>> $err
