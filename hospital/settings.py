"""
Django settings for the hospital backend project.

This configuration aims to be minimal yet functional. It reads common
development values from a `.env` file so that the project can be
configured without modifying source code. In production you should set
environment variables rather than relying on the `.env` file.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv  # type: ignore

# -----------------------------------------------------------------------------
# Base & .env loading
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# -----------------------------------------------------------------------------
# Core flags & security baseline
# -----------------------------------------------------------------------------
ENV = os.getenv("ENV", "dev")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", "0").lower() in {"1", "true", "yes"}

# Allow selected hosts (comma separated). Default for local dev only.
ALLOWED_HOSTS: list[str] = [
    h.strip() for h in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()
]

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY") or "replace-me-with-a-secure-secret-key"

# Now that DEBUG/ALLOWED_HOSTS are defined, enforce prod safeguards
if ENV == "prod":
    if DEBUG:
        raise RuntimeError("DEBUG must be 0 in prod")
    if "*" in ALLOWED_HOSTS:
        raise RuntimeError("ALLOWED_HOSTS cannot contain * in prod")
    if SECRET_KEY == "replace-me-with-a-secure-secret-key":
        raise RuntimeError("SECRET_KEY must be set securely in prod")

# -----------------------------------------------------------------------------
# Applications
# -----------------------------------------------------------------------------
INSTALLED_APPS = [
    "django_prometheus",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "rest_framework",
    "rest_framework.authtoken",
    "drf_yasg",
    # Local apps
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "core.middleware.DeprecatedInquiryMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "hospital.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "hospital.wsgi.application"

# -----------------------------------------------------------------------------
# Database configuration (fixed)
# Priority:
#   1) Explicit MySQL env vars (MYSQL_* or DB_* aliases)
#   2) DATABASE_URL (parsed by dj_database_url)
#   3) SQLite fallback
# -----------------------------------------------------------------------------
DB_CONN_MAX_AGE = int(os.getenv("DB_CONN_MAX_AGE", "120"))

# Support both MYSQL_* and DB_* names for convenience
mysql_name = os.getenv("MYSQL_NAME") or os.getenv("DB_NAME")
mysql_user = os.getenv("MYSQL_USER") or os.getenv("DB_USER")
mysql_password = os.getenv("MYSQL_PASSWORD") or os.getenv("DB_PASSWORD")
mysql_host = os.getenv("MYSQL_HOST") or os.getenv("DB_HOST", "localhost")
mysql_port = os.getenv("MYSQL_PORT") or os.getenv("DB_PORT", "3306")

if mysql_name and mysql_user:
    # MySQL via explicit env vars
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": mysql_name,
            "USER": mysql_user,
            "PASSWORD": mysql_password or "",
            "HOST": mysql_host,
            "PORT": str(mysql_port),
            "CONN_MAX_AGE": DB_CONN_MAX_AGE,
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }
else:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        # Try dj_database_url first
        try:
            import dj_database_url  # type: ignore

            DATABASES = {
                "default": dj_database_url.parse(
                    database_url,
                    conn_max_age=DB_CONN_MAX_AGE,
                )
            }
        except Exception:
            # Fallback to SQLite if parsing fails
            DATABASES = {
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": (BASE_DIR / "db.sqlite3").as_posix(),
                }
            }
    else:
        # Default SQLite for local development
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": (BASE_DIR / "db.sqlite3").as_posix(),
            }
        }

# Optional read-replica (MySQL) via URL, e.g. mysql://user:pass@host:3306/db
DB_REPLICA_URL = os.getenv("DB_REPLICA_URL", "")
if DB_REPLICA_URL:
    from urllib.parse import urlparse

    u = urlparse(DB_REPLICA_URL)
    DATABASES["replica"] = {
        "ENGINE": "django.db.backends.mysql",
        "NAME": (u.path or "").lstrip("/"),
        "USER": u.username,
        "PASSWORD": u.password or "",
        "HOST": u.hostname,
        "PORT": u.port or 3306,
        "CONN_MAX_AGE": DB_CONN_MAX_AGE,
        "OPTIONS": {"charset": "utf8mb4", "connect_timeout": 5},
    }
    DATABASE_ROUTERS = ["core.db_routers.ReadReplicaRouter"]

# -----------------------------------------------------------------------------
# Password validation
# -----------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# -----------------------------------------------------------------------------
# Internationalization & static/media
# -----------------------------------------------------------------------------
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -----------------------------------------------------------------------------
# Auth / DRF
# -----------------------------------------------------------------------------
AUTH_USER_MODEL = "core.User"

REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "patient_write": "60/hour",
        "wx_login": "10/min",
        "anon": "60/min",
        "user": "240/min",
        "login": "10/min",
    },
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "core.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "UNAUTHENTICATED_USER": None,
    "DATETIME_FORMAT": "%Y-%m-%d %H:%M:%S",
    # Use the unified API exception handler
    "EXCEPTION_HANDLER": "core.exceptions.api_exception_handler",
}

# Avoid automatic slash appending to URLs (frontend uses no trailing slash)
APPEND_SLASH = False

# -----------------------------------------------------------------------------
# Swagger / OpenAPI
# -----------------------------------------------------------------------------
SWAGGER_SETTINGS = {
    "DEFAULT_INFO": "hospital.urls.api_info",
}

# -----------------------------------------------------------------------------
# CORS (safe-by-default: none)
# -----------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [
    h.strip() for h in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if h.strip()
]
CORS_ALLOW_CREDENTIALS = True

# -----------------------------------------------------------------------------
# WeChat Mini Program
# -----------------------------------------------------------------------------
WECHAT_ENABLE = os.getenv("WECHAT_ENABLE", "0").lower() in {"1", "true", "yes"}
WECHAT_APPID = os.getenv("WECHAT_APPID", "")
WECHAT_SECRET = os.getenv("WECHAT_SECRET", "")
WECHAT_TIMEOUT = int(os.getenv("WECHAT_TIMEOUT", "5"))
if ENV == "prod" and WECHAT_ENABLE:
    if not WECHAT_APPID or not WECHAT_SECRET:
        raise RuntimeError("WECHAT_APPID/WECHAT_SECRET must be set when WECHAT_ENABLE=1 in prod")

# -----------------------------------------------------------------------------
# Cache (locmem by default; Redis if REDIS_URL present)
# -----------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "hospital-locmem",
    }
}

REDIS_URL = os.getenv("REDIS_URL", "")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "CONNECTION_POOL_KWARGS": {"max_connections": int(os.getenv("REDIS_MAX_CONN", "50"))},
                "SOCKET_CONNECT_TIMEOUT": 3,
                "SOCKET_TIMEOUT": 3,
            },
        }
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

# -----------------------------------------------------------------------------
# Security & proxy headers (enable in prod behind TLS)
# -----------------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
if ENV == "prod":
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "3600"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = False
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "1").lower() in {"1", "true", "yes"}

# -----------------------------------------------------------------------------
# Channels / WebSocket
# -----------------------------------------------------------------------------
ASGI_APPLICATION = "hospital.asgi.application"
CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
}
if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }

# -----------------------------------------------------------------------------
# Upload constraints
# -----------------------------------------------------------------------------
UPLOAD_MAX_MB = int(os.getenv("UPLOAD_MAX_MB", "15"))
ALLOWED_UPLOAD_TYPES = os.getenv("ALLOWED_UPLOAD_TYPES", "image/,application/pdf").split(",")
