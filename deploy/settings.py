"""Settings shared by the two HTTPS deployments."""

import os

from config.settings import *  # noqa: F403

DEBUG = False
SECRET_KEY = os.environ['SECRET_KEY']
DATABASES['default']['NAME'] = '/var/lib/techsnab/db.sqlite3'
DATABASES['reviews']['NAME'] = '/var/lib/techsnab-reviews/reviews.sqlite3'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 86400
