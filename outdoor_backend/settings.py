"""
Django settings for the outdoor_backend project.

Configuration is managed with ``django-configurations``. Settings are
organized into environment-specific classes:

- ``BaseConf``  : settings shared by every environment.
- ``LocalConf`` : local development on a developer machine.
- ``DevConf``   : deployed development / staging environment.
- ``ProdConf``  : production environment with hardened security.

Select the active configuration with the ``DJANGO_CONFIGURATION``
environment variable, e.g. ``DJANGO_CONFIGURATION=LocalConf``.
"""

from datetime import timedelta
from pathlib import Path

from configurations import Configuration, values

BASE_DIR = Path(__file__).resolve().parent.parent


class BaseConf(Configuration):
    """Settings shared across all environments."""

    # No insecure fallback default: production must supply DJANGO_SECRET_KEY.
    SECRET_KEY = values.SecretValue()

    DEBUG = values.BooleanValue(False)

    ALLOWED_HOSTS = values.ListValue([])

    DJANGO_APPS = [
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django.contrib.staticfiles",
    ]

    THIRD_PARTY_APPS = [
        "rest_framework",
        "rest_framework_simplejwt",
        "rest_framework_simplejwt.token_blacklist",
        "corsheaders",
        "drf_yasg",
    ]

    LOCAL_APPS = [
        "apps.common",
        "apps.users",
    ]

    @property
    def INSTALLED_APPS(self):
        return self.DJANGO_APPS + self.THIRD_PARTY_APPS + self.LOCAL_APPS

    MIDDLEWARE = [
        "corsheaders.middleware.CorsMiddleware",
        "django.middleware.security.SecurityMiddleware",
        # Serves static files (e.g. Swagger/ReDoc assets) under gunicorn.
        "whitenoise.middleware.WhiteNoiseMiddleware",
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
        "django.middleware.clickjacking.XFrameOptionsMiddleware",
    ]

    ROOT_URLCONF = "outdoor_backend.urls"

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

    WSGI_APPLICATION = "outdoor_backend.wsgi.application"
    ASGI_APPLICATION = "outdoor_backend.asgi.application"

    DATABASES = values.DatabaseURLValue(
        "postgresql://postgres:postgres@localhost:5432/outdoor",
        environ_name="DATABASE_URL",
        environ_prefix=None,
    )

    AUTH_USER_MODEL = "users.User"

    TEST_RUNNER = "apps.common.test_runner.QuietTestRunner"

    AUTH_PASSWORD_VALIDATORS = [
        {
            "NAME": "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator",
        },
        {
            "NAME": "django.contrib.auth.password_validation."
            "MinimumLengthValidator",
        },
        {
            "NAME": "django.contrib.auth.password_validation."
            "CommonPasswordValidator",
        },
        {
            "NAME": "django.contrib.auth.password_validation."
            "NumericPasswordValidator",
        },
    ]

    LANGUAGE_CODE = "en-us"
    TIME_ZONE = "UTC"
    USE_I18N = True
    USE_TZ = True

    STATIC_URL = "static/"
    STATIC_ROOT = BASE_DIR / "staticfiles"

    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": (
                "whitenoise.storage.CompressedStaticFilesStorage"
            ),
        },
    }

    DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

    REST_FRAMEWORK = {
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "rest_framework_simplejwt.authentication.JWTAuthentication",
        ),
        "DEFAULT_PERMISSION_CLASSES": (
            "rest_framework.permissions.IsAuthenticated",
        ),
        "DEFAULT_PAGINATION_CLASS": (
            "apps.common.pagination.DefaultPagination"
        ),
        "PAGE_SIZE": 20,
        "EXCEPTION_HANDLER": (
            "apps.common.exceptions.custom_exception_handler"
        ),
        "DEFAULT_FILTER_BACKENDS": (
            "rest_framework.filters.SearchFilter",
            "rest_framework.filters.OrderingFilter",
        ),
    }

    # SIMPLE_JWT is built from these values in post_setup().
    JWT_ACCESS_TOKEN_LIFETIME_MINUTES = values.IntegerValue(
        30,
        environ_name="JWT_ACCESS_TOKEN_LIFETIME_MINUTES",
        environ_prefix=None,
    )
    JWT_REFRESH_TOKEN_LIFETIME_DAYS = values.IntegerValue(
        7,
        environ_name="JWT_REFRESH_TOKEN_LIFETIME_DAYS",
        environ_prefix=None,
    )

    CORS_ALLOWED_ORIGINS = values.ListValue(
        ["http://localhost:3000"],
        environ_name="CORS_ALLOWED_ORIGINS",
        environ_prefix=None,
    )
    CORS_ALLOW_CREDENTIALS = True

    SWAGGER_SETTINGS = {
        "USE_SESSION_AUTH": False,
        "SECURITY_DEFINITIONS": {
            "Bearer": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": (
                    "JWT authorization header using the Bearer scheme. "
                    'Example: "Authorization: Bearer <access-token>"'
                ),
            }
        },
    }

    REDOC_SETTINGS = {
        "LAZY_RENDERING": False,
    }

    LOG_LEVEL = values.Value("INFO", environ_name="LOG_LEVEL")

    @property
    def LOGGING(self):
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "verbose": {
                    "format": (
                        "%(asctime)s %(levelname)s %(name)s "
                        "%(message)s"
                    ),
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "verbose",
                },
            },
            "root": {
                "handlers": ["console"],
                "level": self.LOG_LEVEL,
            },
            "loggers": {
                "django": {
                    "handlers": ["console"],
                    "level": self.LOG_LEVEL,
                    "propagate": False,
                },
            },
        }

    @classmethod
    def post_setup(cls):
        """Build derived settings that depend on resolved values."""
        super().post_setup()
        cls.SIMPLE_JWT = {
            "ACCESS_TOKEN_LIFETIME": timedelta(
                minutes=int(cls.JWT_ACCESS_TOKEN_LIFETIME_MINUTES)
            ),
            "REFRESH_TOKEN_LIFETIME": timedelta(
                days=int(cls.JWT_REFRESH_TOKEN_LIFETIME_DAYS)
            ),
            "ROTATE_REFRESH_TOKENS": True,
            "BLACKLIST_AFTER_ROTATION": True,
            "AUTH_HEADER_TYPES": ("Bearer",),
            "USER_ID_FIELD": "id",
            "USER_ID_CLAIM": "user_id",
        }


class LocalConf(BaseConf):
    """Local development configuration."""

    DEBUG = True

    # Insecure default so local development works without extra setup.
    SECRET_KEY = values.Value(
        "django-insecure-local-development-key-change-me",
        environ_name="SECRET_KEY",
    )

    # Local dev only: the frontend host/port isn't fixed yet, so accept any
    # Host header. NEVER do this in Dev/Prod (see BaseConf/ProdConf).
    ALLOWED_HOSTS = ["*"]

    # Local dev only: allow any browser origin. A reflecting regex is used
    # (instead of CORS_ALLOW_ALL_ORIGINS="*") so it still works together with
    # CORS_ALLOW_CREDENTIALS=True, which a wildcard origin cannot.
    CORS_ALLOWED_ORIGIN_REGEXES = [r".*"]


class DevConf(BaseConf):
    """Deployed development / staging configuration."""

    DEBUG = values.BooleanValue(False)

    # Behind a proxy/load balancer that terminates TLS.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


class ProdConf(BaseConf):
    """Production configuration with hardened security."""

    DEBUG = False

    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

    SECURE_SSL_REDIRECT = values.BooleanValue(True)
    SESSION_COOKIE_SECURE = values.BooleanValue(True)
    CSRF_COOKIE_SECURE = values.BooleanValue(True)

    SECURE_HSTS_SECONDS = values.IntegerValue(60 * 60 * 24 * 30)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = values.BooleanValue(True)
    SECURE_HSTS_PRELOAD = values.BooleanValue(True)
    SECURE_CONTENT_TYPE_NOSNIFF = True
