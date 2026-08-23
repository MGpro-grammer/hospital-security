# Create your views here.

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Doctor, Patient, UserKeys
from .permissions import IsDoctor, IsPatient
from .serializers import DoctorSerializer, PatientSerializer, UserKeysSerializer


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

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_keys(request):
    """
    Enregistre les cles de l'utilisateur courant. Une seule fois.

    Le refus d'ecrasement est deliberat : remplacer les cles rendrait tous
    les dossiers existants definitivement illisibles.
    """
    if UserKeys.objects.filter(keycloak_sub=request.user.sub).exists():
        return Response(
            {"detail": "Des cles existent deja pour cet utilisateur."},
            status=status.HTTP_409_CONFLICT,
        )

    serializer = UserKeysSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    # L'identite vient du JETON verifie, jamais du corps de la requete.
    serializer.save(keycloak_sub=request.user.sub)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_keys(request):
    """Renvoie les cles de l'utilisateur courant, et de lui seul."""
    try:
        keys = UserKeys.objects.get(keycloak_sub=request.user.sub)
    except UserKeys.DoesNotExist:
        return Response(
            {"detail": "Aucune cle enregistree."}, status=status.HTTP_404_NOT_FOUND
        )
    return Response(UserKeysSerializer(keys).data)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_profile(request):
    """
    Cree le profil de l'utilisateur courant.

    Le TYPE (patient ou medecin) est deduit du groupe Keycloak porte par le
    jeton, jamais choisi par le client. Un utilisateur ne peut donc pas se
    declarer medecin.
    """
    if request.user.is_patient:
        if Patient.objects.filter(keycloak_sub=request.user.sub).exists():
            return Response({"detail": "Profil deja cree."}, status=status.HTTP_409_CONFLICT)
        serializer = PatientSerializer(data=request.data)
    elif request.user.is_doctor:
        if Doctor.objects.filter(keycloak_sub=request.user.sub).exists():
            return Response({"detail": "Profil deja cree."}, status=status.HTTP_409_CONFLICT)
        serializer = DoctorSerializer(data=request.data)
    else:
        return Response(
            {"detail": "Aucun role attribue a cet utilisateur."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer.is_valid(raise_exception=True)
    serializer.save(keycloak_sub=request.user.sub)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_profile(request):
    """Renvoie le profil de l'utilisateur courant, avec son role."""
    if request.user.is_patient:
        obj = Patient.objects.filter(keycloak_sub=request.user.sub).first()
        if obj:
            return Response({"role": "patient", **PatientSerializer(obj).data})
    elif request.user.is_doctor:
        obj = Doctor.objects.filter(keycloak_sub=request.user.sub).first()
        if obj:
            return Response({"role": "doctor", **DoctorSerializer(obj).data})
    return Response({"detail": "Aucun profil."}, status=status.HTTP_404_NOT_FOUND)