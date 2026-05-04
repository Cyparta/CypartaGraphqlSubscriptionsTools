import os

import django
from django.conf import settings


def pytest_configure():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.django_settings")
    if not settings.configured:
        django.setup()
