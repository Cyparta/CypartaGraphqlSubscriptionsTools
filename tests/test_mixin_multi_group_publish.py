"""Per-group isolation and ``get_subscription_payload`` in mixin."""

from __future__ import annotations

from unittest.mock import patch

import pytest

import CypartaGraphqlSubscriptionsTools.mixins as mixins_mod
from tests.models import MixinPublishTestModel


@pytest.mark.django_db(transaction=True)
def test_second_group_failure_does_not_block_first():
    calls = []

    async def spy(group, payload):
        calls.append((group, payload))
        if group == "BadGroup":
            raise RuntimeError("simulated publish failure")

    with patch.object(
        MixinPublishTestModel,
        "get_subscription_group_names",
        return_value=["OkGroup", "BadGroup"],
    ):
        with patch.object(mixins_mod, "trigger_subscription", spy):
            MixinPublishTestModel.objects.create(title="x")

    assert len(calls) == 2
    assert calls[0][0] == "OkGroup"
    assert calls[1][0] == "BadGroup"


@pytest.mark.django_db(transaction=True)
def test_get_subscription_payload_passed_to_trigger():
    calls = []

    async def spy(group, payload):
        calls.append((group, payload))

    def payload_fn(self, action):
        return {"action": action, "id": self.pk}

    with patch.object(
        MixinPublishTestModel,
        "get_subscription_group_names",
        return_value=["OnlyG"],
    ):
        with patch.object(
            MixinPublishTestModel, "get_subscription_payload", payload_fn
        ):
            with patch.object(mixins_mod, "trigger_subscription", spy):
                MixinPublishTestModel.objects.create(title="p")

    assert len(calls) == 1
    g, pl = calls[0]
    assert g == "OnlyG"
    assert pl["action"] == "create"
    assert "id" in pl
