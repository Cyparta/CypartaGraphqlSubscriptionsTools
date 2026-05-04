from django.views.decorators.csrf import csrf_exempt
from graphene_django.settings import graphene_settings
from graphene_django.views import GraphQLView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny


@csrf_exempt
@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def graphql_token_view(request):
    """GraphiQL / HTTP GraphQL using ``GRAPHENE["SCHEMA"]`` from Django settings."""
    schema = graphene_settings.SCHEMA
    return GraphQLView.as_view(graphiql=True, schema=schema)(request)

