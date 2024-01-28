# your_app/models.py
#from CypartaGraphqlSubscriptionsTools.models import CypartaSubscriptionModelMixin
from .mixins import CypartaSubscriptionModelMixin
from django.db import models
class MyModel(CypartaSubscriptionModelMixin, models.Model):
    name = models.CharField(max_length=100,null=True)
    age=models.IntegerField(default=15)
    
