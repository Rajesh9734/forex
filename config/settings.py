import os
import secrets
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
IS_RENDER = os.environ.get("RENDER") == "true"
DEBUG = not IS_RENDER and os.environ.get("DJANGO_DEBUG", "1") == "1"
DATA_DIR = Path(os.environ.get("DJANGO_DATA_DIR", str(BASE_DIR / "data")))
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if IS_RENDER or not DEBUG:
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY for a production deployment.")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    secret_file = DATA_DIR / ".secret"
    if not secret_file.exists():
        try:
            with secret_file.open("x", encoding="utf-8") as stream:
                stream.write(secrets.token_urlsafe(50))
        except FileExistsError:
            pass
    SECRET_KEY = secret_file.read_text().strip()

ALLOWED_HOSTS = ["127.0.0.1", "localhost", "[::1]"] + [
    host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()
]
render_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if render_hostname:
    ALLOWED_HOSTS.append(render_hostname)
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()
]
REQUIRE_LOGIN = IS_RENDER or not DEBUG or os.environ.get("DJANGO_REQUIRE_LOGIN") == "1"
LOCAL_REPORT_IMPORT_ENABLED = not IS_RENDER
INSTALLED_APPS = [
    "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions",
    "django.contrib.messages", "django.contrib.staticfiles", "journal",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
if REQUIRE_LOGIN:
    MIDDLEWARE.insert(
        MIDDLEWARE.index("django.contrib.auth.middleware.AuthenticationMiddleware") + 1,
        "django.contrib.auth.middleware.LoginRequiredMiddleware",
    )
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "journal.context_processors.workspace",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
database_url = os.environ.get("DATABASE_URL", "")
if database_url:
    DATABASES = {"default": dj_database_url.parse(database_url, conn_max_age=60, conn_health_checks=True)}
    if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
        raise ImproperlyConfigured("DATABASE_URL must identify a PostgreSQL database.")
elif IS_RENDER:
    raise ImproperlyConfigured("Set DATABASE_URL to the Render Postgres internal connection URL.")
else:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.sqlite3", "NAME": DATA_DIR / "backtests.sqlite3",
        "OPTIONS": {"timeout": 30},
    }}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kathmandu"
# MT5 exports contain broker candle times without an offset. Preserve them exactly.
USE_TZ = False
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_ROOT = Path(os.environ.get("DJANGO_MEDIA_ROOT", str(DATA_DIR / "reports")))
MEDIA_URL = "/reports/"
DATA_UPLOAD_MAX_MEMORY_SIZE = 45 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
MT5_REPORTS_DIR = Path(os.environ.get("MT5_REPORTS_DIR", str(
    Path(os.environ.get("APPDATA", str(Path.home()))) / "MetaQuotes" / "Terminal" / "Common" / "Files"
)))
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
SESSION_COOKIE_SECURE = not DEBUG or IS_RENDER
CSRF_COOKIE_SECURE = not DEBUG or IS_RENDER
SECURE_SSL_REDIRECT = not DEBUG or IS_RENDER
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
SECURE_HSTS_SECONDS = 31536000 if not DEBUG or IS_RENDER else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
X_FRAME_OPTIONS = "DENY"
if IS_RENDER:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
