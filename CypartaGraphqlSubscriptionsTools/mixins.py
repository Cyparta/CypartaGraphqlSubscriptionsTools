from django_lifecycle import LifecycleModelMixin, hook
from CypartaGraphqlSubscriptionsTools.events import trigger_subscription
from asgiref.sync import async_to_sync

class CypartaSubscriptionModelMixin(LifecycleModelMixin):

    # Hook triggered after creating an instance of the model
    @hook('after_create')
    def trigger_subscription_on_create(self):
        # Get the model name
        model_name = self.__class__.__name__
        # Trigger the subscription for model creation
        async_to_sync(trigger_subscription)(f"{model_name}Created", self)

    # Hook triggered after updating an instance of the model
    @hook('after_update')
    def trigger_subscription_on_update(self):
        # Get the model name
        model_name = self.__class__.__name__
        # Trigger the subscription for model update
        async_to_sync(trigger_subscription)(f"{model_name}Updated.{self.pk}", self)

    # Hook triggered before deleting an instance of the model
    @hook('before_delete')
    def trigger_subscription_on_delete(self):
        # Get the model name
        model_name = self.__class__.__name__
        # Trigger the subscription for model deletion
        async_to_sync(trigger_subscription)(f"{model_name}Deleted.{self.pk}", self)
