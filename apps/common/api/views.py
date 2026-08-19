from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.api.schema import HEALTH_SCHEMA


class HealthView(APIView):
    """Lightweight process health check.

    Does not touch the database; intended for container / load-balancer
    liveness probes.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @swagger_auto_schema(**HEALTH_SCHEMA)
    def get(self, request):
        return Response({"status": "ok"}, status=status.HTTP_200_OK)
