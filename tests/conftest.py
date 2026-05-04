import os

import django
import pytest
from django.conf import settings

from CypartaGraphqlSubscriptionsTools import events


def pytest_configure():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.django_settings")
    if not settings.configured:
        django.setup()


@pytest.fixture(autouse=True)
def _reset_event_serializer_cache():
    events.reset_event_serializer_cache()
    yield
    events.reset_event_serializer_cache()
