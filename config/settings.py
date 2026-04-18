import os
from pathlib import Path
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG") == "True"

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "").split(",")

CORS_ALLOW_ALL_ORIGINS = True

CSRF_TRUSTED_ORIGINS = [
    "https://mini-proyecto-1-frontend-tau.vercel.app",
    "https://mini-proyecto-1-backend.onrender.com",
]

# Application definition

INSTALLED_APPS = [
    'focusflow',
    'corsheaders',
    'rest_framework',
    'drf_spectacular',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware', # <--- MUÉVELO AQUÍ
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware', # Este siempre debe ir debajo de CorsMiddleware
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv("DATABASE_URL"),
        conn_max_age=600
    )
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',

    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),

    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

# Configuración Simple JWT
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),   # Token de acceso dura 12 horas
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),    # Token de refresh dura 7 días
    "ROTATE_REFRESH_TOKENS": True,                 # Renueva refresh token automáticamente
    "BLACKLIST_AFTER_ROTATION": True,              # Revoca el refresh token usado
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'FocusFlow API',
    'DESCRIPTION': (
        'API REST de FocusFlow: **JWT**, tareas con subtareas, y **carga diaria** (Sprint 3).\n\n'
        '**Base URL del prefijo:** las rutas bajo `config.urls` incluyen el segmento `/tareas/` '
        '(ej. en local: `http://127.0.0.1:8000/tareas/api/...`). El frontend suele definir '
        '`VITE_API_URL` apuntando a ese prefijo (p. ej. `http://127.0.0.1:8000/tareas`).\n\n'
        '**Autorización:** `Authorization: Bearer <access_token>` en las operaciones protegidas.\n\n'
        'Guías: `API_SWAGGER.md`, `SPRINT3.md`.'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'TAGS': [
        {'name': 'Autenticación', 'description': 'Registro, login JWT y refresh de tokens.'},
        {'name': 'Tareas', 'description': 'Listado, creación, edición y borrado de tareas (y subtareas vía `parent`).'},
        {
            'name': 'Carga diaria',
            'description': 'Límite de minutos por día, resumen, simulación, recomendaciones y reprogramación.',
        },
    ],
    'COMPONENT_SPLIT_REQUEST': True,
}

# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/Bogota'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = 'static/'

# Esta es la línea que te falta y que causa el error:
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Opcional: si tienes una carpeta de estáticos en la raíz
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
