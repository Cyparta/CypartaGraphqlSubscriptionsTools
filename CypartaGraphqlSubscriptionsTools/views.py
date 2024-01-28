
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import AllowAny

from rest_framework.decorators import api_view,permission_classes,throttle_classes


from graphene_django.views import GraphQLView
from CypartaGraphqlSubscriptionsTools.schema import schema # Import your GraphQL schema



@csrf_exempt
@api_view(["GET","POST"])
@permission_classes([AllowAny])
def graphql_token_view(request):
    print(request.body)
    #print(schema)
    # print(request)
    #print(request.data)
     #this line is very important he solve mis understand error but he solve is
    #if request.user.is_authenticated:
    return GraphQLView.as_view(graphiql=True, schema=schema)(request)
 
