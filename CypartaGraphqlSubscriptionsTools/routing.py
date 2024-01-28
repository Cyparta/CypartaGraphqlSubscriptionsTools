# your_project/routing.py
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import path 
from django.urls import  re_path
from CypartaGraphqlSubscriptionsTools.consumers import CypartaGraphqlSubscriptionsConsumer




websocket_urlpatterns = [
    
    re_path(r'^ws/graphql/', CypartaGraphqlSubscriptionsConsumer.as_asgi(), ),
    
]