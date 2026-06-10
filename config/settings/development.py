import os

from dotenv import load_dotenv

from .base import *

load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-lna3vfm1)s3i16uj_g#x9i4st$765^-^en=v8l=u+@mt%&_j@!',
)

DEBUG = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = (
    os.environ['ALLOWED_HOSTS'].split(',')
    if os.environ.get('ALLOWED_HOSTS')
    else []
)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 20,
        },
    }
}
