"""CypartaSubscriptionModelMixin publishes on transaction commit only."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.db import transaction

from tests.models import MixinPublishTestModel


@pytest.mark.django_db(transaction=True)
def test_create_publishes_after_commit():
    wrapper = MagicMock()
    with patch(
        "CypartaGraphqlSubscriptionsTools.mixins.async_to_sync", return_value=wrapper
    ):
        MixinPublishTestModel.objects.create(title="commit_ok")
    wrapper.assert_called()


@pytest.mark.django_db(transaction=True)
def test_create_rolled_back_does_not_publish():
    wrapper = MagicMock()
    with patch(
        "CypartaGraphqlSubscriptionsTools.mixins.async_to_sync", return_value=wrapper
    ):
        try:
            with transaction.atomic():
                MixinPublishTestModel.objects.create(title="rollback")
                raise RuntimeError("force rollback")
        except RuntimeError:
            pass
    wrapper.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_should_publish_false_skips_schedule():
    wrapper = MagicMock()
    with patch(
        "CypartaGraphqlSubscriptionsTools.mixins.async_to_sync", return_value=wrapper
    ):
        with patch.object(
            MixinPublishTestModel,
            "should_publish_subscription_event",
            return_value=False,
        ):
            MixinPublishTestModel.objects.create(title="nopublish")
    wrapper.assert_not_called()
