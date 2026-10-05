"""
Django settings for config project — Diễn đàn Khoa TMĐT-Marketing & Công nghệ số.
Xem CLAUDE.md ở thư mục gốc để biết bối cảnh nghiệp vụ đầy đủ.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="django-insecure-change-me")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])


# Application definition

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.humanize",
]

THIRD_PARTY_APPS = [
    "allauth",
    "allauth.account",
    "django_celery_beat",
    "captcha",
    "widget_tweaks",
    "django_ckeditor_5",
]

LOCAL_APPS = [
    "accounts",
    "announcements",
    "forum",
    "groups",
    "interactions",
    "notifications",
    "moderation",
    "dashboard",
    "search",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "notifications.context_processors.notification_bell",
                "search.context_processors.recent_search_bar",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": env("DB_NAME", default=str(BASE_DIR / "db.sqlite3")),
    }
}


# Custom user model

AUTH_USER_MODEL = "accounts.User"


# Password validation + hashing
# Argon2 lam thuat toan hash chinh theo yeu cau bao mat trong CLAUDE.md

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Authentication backends (allauth)

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

SITE_ID = 1

LOGIN_REDIRECT_URL = "home"
LOGIN_URL = "account_login"
ACCOUNT_LOGOUT_REDIRECT_URL = "home"

# Dang nhap/dang ky bang email (khong dung username), bat buoc xac thuc email qua link
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_UNIQUE_EMAIL = True
# Bam link trong email la xac thuc luon (khong can bam them nut "Xac nhan" tren trang web),
# sau do chuyen sang trang dang nhap (mac dinh cua allauth: ve settings.LOGIN_URL)
ACCOUNT_CONFIRM_EMAIL_ON_GET = True
ACCOUNT_RATE_LIMITS = {
    "login_failed": "5/5m/ip,5/5m/key",
}
# Gui email thong bao (khong phai email hanh dong) khi doi/dat lai mat khau thanh cong,
# doi email... - mac dinh allauth la False nen cac template co san (password_changed_*,
# password_reset_*) khong bao gio duoc gui neu khong bat co nay
ACCOUNT_EMAIL_NOTIFICATIONS = True
# Form dang ky rieng: chi cho phep email dung domain truong/khoa (xem accounts/forms.py)
# Form dang nhap rieng: bat buoc giai CAPTCHA sau vai lan dang nhap sai lien tiep
ACCOUNT_FORMS = {
    "signup": "accounts.forms.DomainRestrictedSignupForm",
    "login": "accounts.forms.CaptchaLoginForm",
    "change_password": "accounts.forms.ChangePasswordForm",
}

# Domain email duoc phep dang ky - da chot: @due.udn.vn (Truong Dai hoc Kinh te - DHDN)
ALLOWED_SIGNUP_EMAIL_DOMAINS = env.list("ALLOWED_SIGNUP_EMAIL_DOMAINS", default=["due.udn.vn"])


# Email

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="EC Forum <no-reply@example.com>")


# Redis / Celery (thong bao, rate limiting, backup dinh ky)

REDIS_URL = env("REDIS_URL", default="redis://127.0.0.1:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Ho_Chi_Minh"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
# Chua co Redis server tren may dev - chay task Celery dong bo (trong-process) mac dinh
# de app hoat dong duoc ngay khi demo local. Doi thanh False + chay Redis va celery worker
# that khi trien khai (xem README).
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=DEBUG)
CELERY_TASK_EAGER_PROPAGATES = True

RATELIMIT_USE_CACHE = "default"

# Chua co Redis server tren may dev -> mac dinh dung cache trong bo nho (LocMemCache)
# de rate limiting/cache van hoat dong khi chay local. Bat USE_REDIS_CACHE=True trong .env
# khi da co Redis that (deploy that).
if env.bool("USE_REDIS_CACHE", default=False):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "khoa-forum-locmem",
        }
    }


# Tinh nang nghiep vu dac thu (cau hinh duoc) - xem CLAUDE.md muc "Chua xac dinh"
MAX_PINNED_PER_CATEGORY = env.int("MAX_PINNED_PER_CATEGORY", default=3)


# Internationalization

LANGUAGE_CODE = "vi"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True

# Ban dich rieng cua du an de ghi de cac chuoi tieng Anh cua allauth/captcha
# (2 thu vien nay khong co san ban dich tieng Viet) - xem locale/vi/LC_MESSAGES/django.po
LOCALE_PATHS = [BASE_DIR / "locale"]


# Static / media files

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# CKEditor 5 - trinh soan thao rich text cho noi dung dai (bai dien dan, thong bao, bai nhom).
# Noi dung tra ve la HTML -> luon sanitize bang bleach truoc khi luu (xem config/sanitize.py)
# de tranh XSS, khong tin tuong hoan toan vao gioi han cua editor phia client.
CKEDITOR_5_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
CKEDITOR_5_CONFIGS = {
    "default": {
        "toolbar": [
            "heading", "|",
            "bold", "italic", "underline", "|",
            "bulletedList", "numberedList", "blockQuote", "|",
            "link", "insertImage", "mediaEmbed", "|",
            "undo", "redo",
        ],
        "image": {
            "toolbar": ["imageTextAlternative", "|", "imageStyle:alignLeft", "imageStyle:alignCenter", "imageStyle:alignRight"],
        },
    },
}
