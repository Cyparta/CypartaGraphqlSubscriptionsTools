from django.db import models

from CypartaGraphqlSubscriptionsTools.mixins import CypartaSubscriptionModelMixin


class MixinPublishTestModel(CypartaSubscriptionModelMixin, models.Model):
    title = models.CharField(max_length=40, default="t")
