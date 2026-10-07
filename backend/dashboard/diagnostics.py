"""Point d’entrée de diagnostic client, actif uniquement en mode debug.

Il ne reçoit aucun secret : seulement l’état technique du navigateur au moment d’un échec
d’authentification (instance de page, présence d’un jeton, disponibilité du stockage, iframe).
"""
import logging

from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger("kemta")

_ALLOWED_FIELDS = (
    "client",
    "path",
    "status",
    "hadToken",
    "tokenLength",
    "storage",
    "inIframe",
    "cookiesEnabled",
    "topReferrer",
    "pageUrl",
    "visibility",
    "flow",
)


class ClientDiagnosticAPIView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def post(self, request):
        if not settings.DEBUG:
            return Response(status=404)
        reported = {field: str(request.data.get(field, "-"))[:120] for field in _ALLOWED_FIELDS}
        logger.info("client.diagnostic " + " ".join(f"{key}={value}" for key, value in reported.items()))
        return Response(status=204)
