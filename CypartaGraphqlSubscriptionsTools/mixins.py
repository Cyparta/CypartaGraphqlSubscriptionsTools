import logging

from asgiref.sync import async_to_sync
from django.db import transaction
from django_lifecycle import LifecycleModelMixin, hook

from CypartaGraphqlSubscriptionsTools.events import trigger_subscription

logger = logging.getLogger(__name__)


class CypartaSubscriptionModelMixin(LifecycleModelMixin):
    def should_publish_subscription_event(self, action: str) -> bool:
        """Return whether to schedule channel publishes for ``action`` (create/update/delete)."""
        return True

    def get_subscription_group_names(self, action: str) -> list[str]:
        """
        Channel group names to publish for this instance.

        Default pattern: ``{ModelName}Created``, ``{ModelName}Updated.{pk}``,
        ``{ModelName}Deleted.{pk}``.
        """
        model_name = self.__class__.__name__
        if action == "create":
            return [f"{model_name}Created"]
        if action == "update":
            return [f"{model_name}Updated.{self.pk}"]
        if action == "delete":
            return [f"{model_name}Deleted.{self.pk}"]
        return []

    def get_subscription_payload(self, action: str):
        """Value passed to ``trigger_subscription`` for each group (default: ``self``)."""
        return self

    def _schedule_subscription_triggers(self, action: str) -> None:
        if not self.should_publish_subscription_event(action):
            return
        groups = list(self.get_subscription_group_names(action))
        if not groups:
            return
        payload = self.get_subscription_payload(action)

        def _after_commit() -> None:
            for group in groups:
                try:
                    async_to_sync(trigger_subscription)(group, payload)
                except Exception:
                    logger.exception(
                        "subscription publish failed after_commit action=%s group=%s",
                        action,
                        group,
                    )

        transaction.on_commit(_after_commit)

    @hook("after_create")
    def trigger_subscription_on_create(self):
        self._schedule_subscription_triggers("create")

    @hook("after_update")
    def trigger_subscription_on_update(self):
        self._schedule_subscription_triggers("update")

    @hook("after_delete")
    def trigger_subscription_on_delete(self):
        self._schedule_subscription_triggers("delete")
