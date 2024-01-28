from django.urls import path,include
from django.conf import settings
from django.conf.urls.static import static



from .views import *








urlpatterns = [
    

path('graphql/', graphql_token_view,),


]




if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)






