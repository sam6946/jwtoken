import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [entry.strip() for entry in os.getenv(name, default).split(",") if entry.strip()]


DEBUG = env_bool("DJANGO_DEBUG", default=os.getenv("DJANGO_ENV", "development") != "production")
SECRET_KEY = os.getenv("SECRET_KEY", "unsafe-development-key-change-before-production")
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0")
for local_host in ("localhost", "127.0.0.1"):
    if local_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(local_host)
if DEBUG and "testserver" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("testserver")

# Hôtes supplémentaires (prévisualisations distantes, IP internes). Un préfixe « . » autorise les sous-domaines.
ALLOWED_HOSTS += env_list("EXTRA_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "common.apps.CommonConfig",
    "accounts.apps.AccountsConfig",
    "service_requests.apps.ServiceRequestsConfig",
    "projects.apps.ProjectsConfig",
    "companies.apps.CompaniesConfig",
    "opportunities.apps.OpportunitiesConfig",
    "notifications.apps.NotificationsConfig",
    "payments.apps.PaymentsConfig",
    "dashboard.apps.DashboardConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "common.middleware.RequestIdMiddleware",
    "common.middleware.ApiDiagnosticsMiddleware",
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
ASGI_APPLICATION = "config.asgi.application"

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL:
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=not DEBUG)}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Douala"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

OBJECT_STORAGE_ENDPOINT = os.getenv("OBJECT_STORAGE_ENDPOINT", "")
OBJECT_STORAGE_BUCKET = os.getenv("OBJECT_STORAGE_BUCKET", "")
if OBJECT_STORAGE_ENDPOINT and OBJECT_STORAGE_BUCKET:
    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
    AWS_S3_ENDPOINT_URL = OBJECT_STORAGE_ENDPOINT
    AWS_STORAGE_BUCKET_NAME = OBJECT_STORAGE_BUCKET
    AWS_ACCESS_KEY_ID = os.getenv("OBJECT_STORAGE_ACCESS_KEY", "")
    AWS_SECRET_ACCESS_KEY = os.getenv("OBJECT_STORAGE_SECRET_KEY", "")
    AWS_S3_REGION_NAME = os.getenv("OBJECT_STORAGE_REGION", "auto")
    AWS_S3_USE_SSL = env_bool("OBJECT_STORAGE_USE_SSL", default=True)
    AWS_QUERYSTRING_AUTH = True
    AWS_DEFAULT_ACL = None
    AWS_S3_FILE_OVERWRITE = False
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_S3_CUSTOM_DOMAIN = os.getenv("OBJECT_STORAGE_CUSTOM_DOMAIN") or None
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }

REDIS_URL = os.getenv("REDIS_URL", "")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
            "KEY_PREFIX": "kemta",
            "TIMEOUT": 300,
        }
    }
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "kemta-local"}}

def _throttle_rates(rates: dict, debug: bool | None = None) -> dict:
    """Applique un facteur de tolérance aux limites anti-abus.

    Les valeurs ci-dessous sont celles de la production : elles protègent les
    formulaires publics (demandes de service, connexions, codes OTP). En
    développement ou en démonstration, la recette automatisée enchaîne les envois,
    ce qui déclenche légitimement ces limites. La variable
    `KEMTA_THROTTLE_FACTOR` (défaut 1, ignorée en production) permet de les
    assouplir localement sans jamais modifier les réglages de production.
    """
    is_debug = DEBUG if debug is None else debug
    factor = 1
    if is_debug:
        try:
            factor = max(1, int(os.getenv("KEMTA_THROTTLE_FACTOR", "1")))
        except ValueError:
            factor = 1
    if factor == 1:
        return rates
    adjusted = {}
    for scope, rate in rates.items():
        try:
            count, period = rate.split("/")
            adjusted[scope] = f"{int(count) * factor}/{period}"
        except ValueError:
            adjusted[scope] = rate
    return adjusted


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "accounts.authentication.KemtaJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "common.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": _throttle_rates({
        "anon": "90/minute",
        "user": "180/minute",
        "otp": "5/hour",
        "auth_login": "10/minute",
        "auth_register": "5/hour",
        "auth_reset": "5/hour",
        "service_request": "10/hour",
        "company_public": "120/minute",
        "opportunity_public": "90/minute",
    }),
    "DEFAULT_RENDERER_CLASSES": (
        ["rest_framework.renderers.JSONRenderer", "rest_framework.renderers.BrowsableAPIRenderer"]
        if DEBUG
        else ["rest_framework.renderers.JSONRenderer"]
    ),
    "COERCE_DECIMAL_TO_STRING": True,
}

from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=10),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "ALGORITHM": "HS256",
    "SIGNING_KEY": os.getenv("JWT_SECRET", SECRET_KEY),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

REFRESH_COOKIE_NAME = "kemta_refresh"
REFRESH_COOKIE_SECURE = env_bool("REFRESH_COOKIE_SECURE", default=not DEBUG)
# « None » + Partitioned permet au cookie de session de fonctionner dans un aperçu embarqué (iframe),
# où les navigateurs bloquent les cookies tiers. À conserver sur « Lax » hors contexte embarqué.
REFRESH_COOKIE_SAMESITE = os.getenv("REFRESH_COOKIE_SAMESITE", "Lax").strip().capitalize()
REFRESH_COOKIE_PARTITIONED = env_bool("REFRESH_COOKIE_PARTITIONED", default=False)
REFRESH_COOKIE_PATH = "/api/v1/auth/"
# Le cookie HttpOnly reste la voie normale. En développement (aperçu embarqué qui bloque les
# cookies tiers), l'API peut aussi renvoyer le refresh token afin que l'onglet puisse renouveler
# sa session sans cookie. Toujours laisser désactivé en production.
REFRESH_TOKEN_IN_BODY = env_bool("REFRESH_TOKEN_IN_BODY", default=DEBUG)
# Certains proxys d'aperçu retirent l'en-tête Authorization en transit : l'API accepte
# alors le même jeton dans X-Kemta-Auth. Désactivé hors développement.
ALLOW_TOKEN_AUTH_HEADER_FALLBACK = env_bool("ALLOW_TOKEN_AUTH_HEADER_FALLBACK", default=DEBUG)
OTP_TTL_SECONDS = int(os.getenv("OTP_TTL_SECONDS", "300"))
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
SMS_PROVIDER = os.getenv("SMS_PROVIDER", "console").strip().lower()
SMS_API_URL = os.getenv("SMS_API_URL", "")
SMS_API_KEY = os.getenv("SMS_API_KEY", "")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "notifications@localhost")
EMAIL_BACKEND = (
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG and not EMAIL_HOST
    else "django.core.mail.backends.smtp.EmailBackend"
)

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL or "memory://")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL or "cache+memory://")
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", default=DEBUG)
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_BEAT_SCHEDULE = {
    "cleanup-expired-otp-cache": {
        "task": "notifications.tasks.cleanup_expired_otp_cache",
        "schedule": 60 * 60,
    },
}

PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "").strip().lower()
PAYMENT_API_KEY = os.getenv("PAYMENT_API_KEY", "")
PAYMENT_WEBHOOK_SECRET = os.getenv("PAYMENT_WEBHOOK_SECRET", "")

if env_bool("TRUST_PROXY_SSL_HEADER", default=False):
    # Derrière Nginx ou un proxy de prévisualisation : l'API reçoit X-Forwarded-Proto: https.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", default=False)
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
DATA_UPLOAD_MAX_MEMORY_SIZE = 48 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024

LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", "INFO").upper()
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {"format": "{asctime} {levelname} {name} request_id={request_id} {message}", "style": "{"},
        "plain": {"format": "{asctime} {levelname} {name} {message}", "style": "{"},
    },
    "filters": {"request_id": {"()": "common.logging.RequestIdFilter"}},
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "structured", "filters": ["request_id"]},
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "kemta": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}
