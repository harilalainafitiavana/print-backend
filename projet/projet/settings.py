
from datetime import timedelta
from pathlib import Path
from decouple import config
from corsheaders.defaults import default_headers
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config("SECRET_KEY", default="django-insecure-mevnbhiqf^t0o_3u0qhz(=914l!)x25o9k%qj)bqlx5&7lj43f")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config("DEBUG", default=True, cast=bool)


ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    ".railway.app",  # le point permet tous les sous-domaines Railway
]



# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'print',
]


REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}


MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

CORS_ALLOW_ALL_ORIGINS = True  

ROOT_URLCONF = 'projet.urls'

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

WSGI_APPLICATION = 'projet.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'Printmg',     
#         'USER': 'fiti',   
#         'PASSWORD': 'fiti', 
#         'HOST': 'localhost',           
#         'PORT': '5432',       
#     }
# }

DATABASES = {
    "default": dj_database_url.config(
        default=config("DATABASE_URL")  # utilisera DATABASE_URL si elle est définie
        # default="postgres://fiti:fiti@localhost:5432/Printmg"
    )
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / "staticfiles"

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
# pour ne pas ouvrir l'API à tout le monde
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",  # React avec Vite
    # "http://127.0.0.1:5173",
    # "https://ton-frontend.up.railway.app",
]


CORS_ALLOW_HEADERS = list(default_headers) + [
    "authorization",
]

CORS_ALLOW_CREDENTIALS = True # autoriser l’envoi de cookies et headers sensibles (comme le JWT).

MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = '/media/'

AUTH_USER_MODEL = "print.Utilisateurs"

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',  # Authentification par défaut
    'print.auth_backend.EmailBackend',  # Notre backend personnalisé
]

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=3),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "USER_ID_FIELD": "id", # quel champ du modèle User est utilisé comme identifiant interne dans le token.
    "USER_ID_CLAIM": "user_id", # comment ce champ sera nommé dans le payload du token JWT
}


EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# 🔹 Serveur Gmail
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True


# 🔹Compte Gmail (expéditeur)
EMAIL_HOST_USER = config("EMAIL_HOST_USER")
# IMPORTANT : utilise un "mot de passe d’application" Google
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD")

# Par défaut, Django utilisera cet expéditeur
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# 🔹 Clé API OpenAI
GEMINI_API_KEY = config("GEMINI_API_KEY")


