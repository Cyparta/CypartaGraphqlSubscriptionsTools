from django.db import models

from CypartaGraphqlSubscriptionsTools.mixins import CypartaSubscriptionModelMixin


class MyModel(CypartaSubscriptionModelMixin, models.Model):
    """Demo model for local development only (see ``examples/README.md``)."""

    name = models.CharField(max_length=100, null=True, blank=True)
    age = models.IntegerField(default=15)
