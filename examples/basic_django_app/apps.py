from django.apps import AppConfig


class BasicDjangoAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "examples.basic_django_app"
    label = "cyparta_demo_basic"
    verbose_name = "Cyparta demo (basic Django app)"
