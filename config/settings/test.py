import os
from pathlib import Path

from .development import *

BASE_DIR_SETTINGS = Path(__file__).resolve().parent.parent.parent
TEST_DB_DIR = BASE_DIR_SETTINGS / 'e2e'
TEST_DB_DIR.mkdir(exist_ok=True)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': str(TEST_DB_DIR / 'test_db.sqlite3'),
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

SESSION_COOKIE_SECURE = False
