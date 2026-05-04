"""Ensure the installable package does not register demo models or require examples."""

from django.apps import apps


def test_cyparta_app_has_no_concrete_models():
    cfg = apps.get_app_config("CypartaGraphqlSubscriptionsTools")
    names = [m.__name__ for m in cfg.get_models()]
    assert "MyModel" not in names
    assert names == []


def test_import_consumers_without_examples_installed():
    from CypartaGraphqlSubscriptionsTools.consumers import CypartaGraphqlSubscriptionsConsumer

    assert CypartaGraphqlSubscriptionsConsumer.__name__ == "CypartaGraphqlSubscriptionsConsumer"


def test_import_package_namespace():
    import CypartaGraphqlSubscriptionsTools

    assert CypartaGraphqlSubscriptionsTools.__spec__.name == "CypartaGraphqlSubscriptionsTools"
