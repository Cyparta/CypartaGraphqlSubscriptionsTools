"""Minimal Django settings for pytest (library has no project package)."""

SECRET_KEY = "test-secret-key"
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "channels",
    "rest_framework",
    "rest_framework.authtoken",
    "CypartaGraphqlSubscriptionsTools",
    "tests.apps.TestsConfig",
]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
}
CYPARTA_WS_OUTBOX_MAXSIZE = 8
