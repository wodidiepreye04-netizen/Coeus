from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-^&2$6ewpame$&5t=r8r_4h@*5ev&qpoeth^ou)k1wvx8bw=nni'

DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'coeus.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'coeus.wsgi.application'

import dj_database_url
import os

DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('postgresql://neondb_owner:npg_Tn5uajbz4VxH@ep-summer-tooth-b8u50573-pooler.c-14.us-east-1.aws.neon.tech/neondb?channel_binding=require&sslmode=require')
    )
}
    }
}

AUTH_USER_MODEL = 'core.CoeusUser'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Lagos'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/signin'
LOGIN_REDIRECT_URL = '/dashboard'
LOGOUT_REDIRECT_URL = '/'

# ─── Payment & Subscription Settings ──────────────────────────────────────────
import os

PAYSTACK_PUBLIC_KEY = os.environ.get('PAYSTACK_PUBLIC_KEY', 'pk_test_sample_coeus_key')
PAYSTACK_SECRET_KEY = os.environ.get('PAYSTACK_SECRET_KEY', 'sk_test_sample_coeus_key')

PERSONAL_BANK_DETAILS = {
    'bank_name': 'Kuda Microfinance Bank',
    'account_number': '2019284756',
    'account_name': 'Diepreye Wodi / COEUS Mental Care',
    'sort_code': '090267',
    'support_phone': '+234 812 345 6789',
    'support_email': 'payments@coeus.ng',
}

SUBSCRIPTION_PLANS = {
    'basic': {
        'id': 'basic',
        'name': 'Basic',
        'price': 25000,
        'duration_days': 30,
        'sessions': 4,
        'tagline': 'Four private conversations a month for steady, personal support.',
        'features': [
            '4 individual sessions a month',
            'Direct appointment scheduling',
            'Encrypted private reflection journal',
            'Discreet personal safety plan',
        ],
    },
    'pro': {
        'id': 'pro',
        'name': 'Pro',
        'price': 45000,
        'duration_days': 30,
        'sessions': 8,
        'popular': True,
        'tagline': 'Eight private conversations a month for deeper, ongoing guidance.',
        'features': [
            '8 individual sessions a month',
            'Twice-weekly session rhythm',
            'Priority clinician matching',
            'Encrypted private reflection journal',
            'Personal safety plan with direct check-ins',
        ],
    },
    'max': {
        'id': 'max',
        'name': 'Max',
        'price': 65000,
        'duration_days': 30,
        'sessions': 12,
        'tagline': 'Twelve private conversations a month for comprehensive, intensive care.',
        'features': [
            '12 individual sessions a month',
            'Flexible, comprehensive scheduling',
            'Dedicated lead clinician partnership',
            'Encrypted private reflection journal',
            'Full personal care toolkit access',
        ],
    },
}
