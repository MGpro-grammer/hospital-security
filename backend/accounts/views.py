# Create your views here.

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Endpoint public : verifie seulement que l'API repond."""
    return Response({"status": "ok"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    """Renvoie l'identite deduite du jeton. Aucun acces a la base."""
    user = request.user
    return Response({
        "sub": user.sub,
        "username": user.username,
        "is_patient": user.is_patient,
        "is_doctor": user.is_doctor,
    })
