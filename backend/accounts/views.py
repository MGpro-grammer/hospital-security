# Create your views here.

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from records.models import MedicalFile, WrappedKey

from .models import Doctor, DoctorPatientLink, Patient, UserKeys
from .permissions import IsDoctor, IsPatient
from .serializers import (
    DoctorPublicSerializer,
    DoctorSerializer,
    LinkSerializer,
    PatientPublicSerializer,
    PatientSerializer,
    UserKeysSerializer,
)


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

def _enregistrer_cles_rechiffrees(link, cles_rechiffrees):
    """
    Enregistre les DEK rechiffrees par le patient pour un medecin.

    Le SERVEUR NE PEUT PAS produire ces cles : il ne sait pas dechiffrer
    les DEK. Il ne fait que stocker ce que le patient a calcule dans son
    navigateur. C'est ce qui garantit qu'un administrateur ne peut pas
    s'octroyer l'acces a un dossier.

    @param link: le DoctorPatientLink concerne
    @param cles_rechiffrees: [{file_id, wrapped_dek}, ...]
    """
    fichiers_du_dossier = set(
        MedicalFile.objects.filter(patient_id=link.patient_id).values_list(
            "id", flat=True
        )
    )

    a_creer = []
    for entree in cles_rechiffrees:
        file_id = entree.get("file_id")
        wrapped = entree.get("wrapped_dek")
        if not file_id or not wrapped:
            continue
        # Un patient ne peut donner acces qu'a SES PROPRES fichiers.
        if str(file_id) not in {str(f) for f in fichiers_du_dossier}:
            continue
        a_creer.append(
            WrappedKey(
                file_id=file_id,
                recipient_sub=link.doctor_id,
                wrapped_dek=wrapped,
            )
        )

    # `ignore_conflicts=True` ignore silencieusement les cles deja
    # presentes, et ne renseigne pas les cles primaires en retour. On
    # compte donc de part et d'autre : un chiffre approximatif dans une
    # interface de securite finit toujours par tromper quelqu'un.
    filtre = WrappedKey.objects.filter(recipient_sub=link.doctor_id)
    avant = filtre.count()
    WrappedKey.objects.bulk_create(a_creer, ignore_conflicts=True)
    return filtre.count() - avant


@api_view(["GET"])
@permission_classes([IsPatient])
def list_doctors(request):
    """
    Liste les medecins, filtrable par nom. Reserve aux patients.

    Le filtre passe exclusivement par l'ORM Django : aucune requete SQL
    construite par concatenation, donc aucune surface d'injection.
    """
    recherche = request.query_params.get("q", "").strip()
    medecins = Doctor.objects.all()
    if recherche:
        medecins = medecins.filter(
            Q(last_name__icontains=recherche) | Q(first_name__icontains=recherche)
        )
    return Response(DoctorPublicSerializer(medecins[:50], many=True).data)

@api_view(["GET"])
@permission_classes([IsDoctor])
def list_patients(request):
    """
    Recherche un patient par nom. Reserve aux medecins.

    Un medecin doit pouvoir DEMANDER l'acces a un dossier ; il lui faut
    donc pouvoir designer le patient. La reponse ne contient que le nom
    et l'identifiant : aucune donnee medicale, aucune cle, aucun fichier.

    Le terme de recherche est OBLIGATOIRE. Sans lui, on ne renvoie rien.
    Un medecin n'a aucune raison legitime d'obtenir l'annuaire complet
    des patients de l'hopital : ce serait une fuite massive pour un seul
    compte compromis.
    """
    recherche = request.query_params.get("q", "").strip()
    if not recherche:
        return Response([])

    patients = Patient.objects.filter(
        Q(last_name__icontains=recherche) | Q(first_name__icontains=recherche)
    )
    return Response(PatientPublicSerializer(patients[:50], many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_links(request):
    """Liste les liens de l'utilisateur courant, patient ou medecin."""
    if getattr(request.user, "is_patient", False):
        liens = DoctorPatientLink.objects.filter(patient_id=request.user.sub)
    elif getattr(request.user, "is_doctor", False):
        liens = DoctorPatientLink.objects.filter(doctor_id=request.user.sub)
    else:
        liens = DoctorPatientLink.objects.none()
    return Response(LinkSerializer(liens, many=True).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_link(request):
    """
    Cree un lien medecin-patient.

    Initie par le PATIENT  -> approuve immediatement. Le patient fournit
                              dans la MEME requete les DEK rechiffrees.
    Initie par un MEDECIN  -> cree EN ATTENTE. Aucune cle n'est transmise :
                              un medecin ne peut pas s'octroyer l'acces.
    """
    est_patient = getattr(request.user, "is_patient", False)
    est_medecin = getattr(request.user, "is_doctor", False)

    if est_patient:
        patient_id = request.user.sub
        doctor_id = request.data.get("doctor_sub")
        statut = DoctorPatientLink.Status.APPROVED
        initiateur = DoctorPatientLink.Initiator.PATIENT
    elif est_medecin:
        doctor_id = request.user.sub
        patient_id = request.data.get("patient_sub")
        statut = DoctorPatientLink.Status.PENDING
        initiateur = DoctorPatientLink.Initiator.DOCTOR
    else:
        return Response(
            {"detail": "Aucun role attribue."}, status=status.HTTP_403_FORBIDDEN
        )

    if not doctor_id or not patient_id:
        return Response(
            {"detail": "Identifiant manquant."}, status=status.HTTP_400_BAD_REQUEST
        )
    if not Doctor.objects.filter(keycloak_sub=doctor_id).exists():
        return Response({"detail": "Medecin inconnu."}, status=status.HTTP_404_NOT_FOUND)
    if not Patient.objects.filter(keycloak_sub=patient_id).exists():
        return Response({"detail": "Patient inconnu."}, status=status.HTTP_404_NOT_FOUND)
    if DoctorPatientLink.objects.filter(
        patient_id=patient_id, doctor_id=doctor_id
    ).exists():
        return Response(
            {"detail": "Un lien existe deja."}, status=status.HTTP_409_CONFLICT
        )

    with transaction.atomic():
        lien = DoctorPatientLink.objects.create(
            patient_id=patient_id,
            doctor_id=doctor_id,
            status=statut,
            initiated_by=initiateur,
            approved_at=timezone.now() if est_patient else None,
        )
        nb = 0
        if est_patient:
            nb = _enregistrer_cles_rechiffrees(
                lien, request.data.get("rewrapped_keys", [])
            )

    return Response(
        {**LinkSerializer(lien).data, "cles_partagees": nb},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsPatient])
def approve_link(request, link_id):
    """
    Le patient approuve une demande d'un medecin et lui donne l'acces.

    L'approbation et le partage des cles sont indissociables : approuver
    sans fournir de cles donnerait un acces vide, et fournir des cles sans
    approuver contournerait le consentement.
    """
    lien = DoctorPatientLink.objects.filter(
        id=link_id, patient_id=request.user.sub
    ).first()
    if lien is None:
        return Response({"detail": "Introuvable."}, status=status.HTTP_404_NOT_FOUND)
    if lien.status == DoctorPatientLink.Status.APPROVED:
        return Response(
            {"detail": "Lien deja approuve."}, status=status.HTTP_409_CONFLICT
        )

    with transaction.atomic():
        lien.status = DoctorPatientLink.Status.APPROVED
        lien.approved_at = timezone.now()
        lien.save(update_fields=["status", "approved_at"])
        nb = _enregistrer_cles_rechiffrees(
            lien, request.data.get("rewrapped_keys", [])
        )

    return Response({**LinkSerializer(lien).data, "cles_partagees": nb})


@api_view(["DELETE"])
@permission_classes([IsPatient])
def delete_link(request, link_id):
    """
    Retire un medecin du dossier.

    Supprime le lien ET toutes ses cles de dechiffrement. Le medecin perd
    l'acces a tous les fichiers, presents et futurs.

    LIMITE INHERENTE AU CHIFFREMENT DE BOUT EN BOUT : un fichier deja
    telecharge et dechiffre par le medecin reste en sa possession. Aucun
    systeme ne peut reprendre une donnee deja livree. Cette limite est
    documentee et assumee.
    """
    lien = DoctorPatientLink.objects.filter(
        id=link_id, patient_id=request.user.sub
    ).first()
    if lien is None:
        return Response({"detail": "Introuvable."}, status=status.HTTP_404_NOT_FOUND)

    with transaction.atomic():
        supprimees = WrappedKey.objects.filter(
            file__patient_id=lien.patient_id, recipient_sub=lien.doctor_id
        ).delete()[0]
        lien.delete()

    return Response({"detail": "Medecin retire.", "cles_supprimees": supprimees})

@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def revoke_account(request):
    """
    REVOCATION D'UN COMPTE (ecart d'audit n°5).

    `health.pdf` intitule sa section « User registration, authentication
    AND REVOCATION ». Le retrait d'un medecin de la liste d'un patient
    (Phase 7) ne couvre que la RELATION, pas le COMPTE.

    Que se passe-t-il quand un medecin quitte son organisation ?

    La revocation a DEUX etages, et les deux sont necessaires :

      1. KEYCLOAK  -- un administrateur desactive le compte. Plus aucun
         jeton n'est emis, et les jetons deja emis expirent en quelques
         minutes. L'utilisateur ne peut plus s'AUTHENTIFIER.

      2. APPLICATION (ici) -- tout son materiel cryptographique est
         detruit : ses cles, ses liens, et surtout les DEK chiffrees a
         son nom. Meme muni d'un jeton encore valide, il n'aurait plus
         RIEN a dechiffrer.

    Le second etage est le seul qui compte vraiment. Un controle d'acces
    peut etre contourne ; une cle detruite ne revient pas.

    LIMITE ASSUMEE : un fichier deja telecharge et dechiffre reste en sa
    possession. Aucun systeme ne reprend une donnee deja livree.
    """
    sub = request.user.sub

    with transaction.atomic():
        # 1. Les DEK chiffrees a son nom. Sans elles, les blocs chiffres
        #    des dossiers auxquels il avait acces lui sont definitivement
        #    illisibles.
        cles_supprimees = WrappedKey.objects.filter(recipient_sub=sub).delete()[0]

        # 2. Ses liens. La suppression du profil les emporterait en
        #    cascade ; on les compte explicitement pour la tracabilite.
        liens_supprimes = DoctorPatientLink.objects.filter(
            Q(patient_id=sub) | Q(doctor_id=sub)
        ).delete()[0]

        # 3. Son profil. Pour un PATIENT, la cascade emporte aussi ses
        #    fichiers medicaux et son manifeste : son dossier disparait.
        Patient.objects.filter(keycloak_sub=sub).delete()
        Doctor.objects.filter(keycloak_sub=sub).delete()

        # 4. Ses propres cles. Apres cette ligne, meme LUI ne peut plus
        #    rien dechiffrer : sa cle privee chiffree n'existe plus.
        UserKeys.objects.filter(keycloak_sub=sub).delete()

    return Response({
        "detail": "Compte revoque. Materiel cryptographique detruit.",
        "cles_supprimees": cles_supprimees,
        "liens_supprimes": liens_supprimes,
    })