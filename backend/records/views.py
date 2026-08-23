from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import DoctorPatientLink

from .models import MedicalFile, RecordManifest, WrappedKey
from .serializers import (
    FileUploadSerializer,
    ManifestSerializer,
    MedicalFileSerializer,
)


def can_access_record(user, patient_sub):
    """
    CONTROLE D'ACCES OBJET PAR OBJET.

    Un patient n'accede qu'a SON PROPRE dossier. Un medecin n'accede a un
    dossier que si un lien APPROUVE existe. Toute autre situation : refus.

    Cette fonction est appelee sur CHAQUE endpoint, sans exception. Le role
    porte par le jeton ne suffit pas : etre medecin n'ouvre aucun dossier
    en particulier.

    @param user: utilisateur reconstruit depuis le jeton verifie
    @param patient_sub: identifiant du proprietaire du dossier
    @return: True si l'acces est legitime
    """
    if getattr(user, "is_patient", False):
        return user.sub == patient_sub
    if getattr(user, "is_doctor", False):
        return DoctorPatientLink.objects.filter(
            patient_id=patient_sub,
            doctor_id=user.sub,
            status=DoctorPatientLink.Status.APPROVED,
        ).exists()
    return False


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_file(request):
    """
    Depose un fichier chiffre dans un dossier medical.

    Depot par le PATIENT   -> approuve immediatement, manifeste mis a jour.
    Depot par un MEDECIN   -> en attente d'approbation, manifeste inchange
                              (le fichier n'entre dans le dossier signe
                              qu'une fois approuve par le patient).
    """
    serializer = FileUploadSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    patient_sub = data["patient_sub"]

    if not can_access_record(request.user, patient_sub):
        return Response({"detail": "Acces refuse."}, status=status.HTTP_403_FORBIDDEN)

    est_patient = getattr(request.user, "is_patient", False)

    if est_patient:
        manquant = [
            champ
            for champ in ("manifest_content", "manifest_signature", "manifest_version")
            if data.get(champ) in (None, "")
        ]
        if manquant:
            return Response(
                {"detail": f"Manifeste requis : {', '.join(manquant)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        actuel = RecordManifest.objects.filter(patient_id=patient_sub).first()
        if actuel and data["manifest_version"] <= actuel.version:
            # Compteur monotone : bloque le rejeu d'un ancien manifeste
            # par un attaquant externe muni d'un jeton vole.
            return Response(
                {"detail": "Version de manifeste obsolete."},
                status=status.HTTP_409_CONFLICT,
            )

    with transaction.atomic():
        fichier = MedicalFile.objects.create(
            patient_id=patient_sub,
            ciphertext=data["ciphertext"],
            iv=data["iv"],
            status=(
                MedicalFile.Status.APPROVED
                if est_patient
                else MedicalFile.Status.PENDING_APPROVAL
            ),
            uploaded_by=request.user.sub,
        )

        WrappedKey.objects.bulk_create(
            [
                WrappedKey(
                    file=fichier,
                    recipient_sub=cle["recipient_sub"],
                    wrapped_dek=cle["wrapped_dek"],
                )
                for cle in data["wrapped_keys"]
            ]
        )

        if est_patient:
            RecordManifest.objects.update_or_create(
                patient_id=patient_sub,
                defaults={
                    "content": data["manifest_content"],
                    "signature": data["manifest_signature"],
                    "version": data["manifest_version"],
                },
            )

    return Response(
        {"id": str(fichier.id), "status": fichier.status},
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_record(request, patient_sub):
    """
    Liste les fichiers d'un dossier ET son manifeste signe.

    Les deux sont renvoyes ensemble a dessein : le client peut verifier en
    un seul aller-retour que la liste livree correspond a la liste signee.
    """
    if not can_access_record(request.user, patient_sub):
        return Response({"detail": "Acces refuse."}, status=status.HTTP_403_FORBIDDEN)

    fichiers = MedicalFile.objects.filter(patient_id=patient_sub)
    manifeste = RecordManifest.objects.filter(patient_id=patient_sub).first()

    return Response(
        {
            "files": MedicalFileSerializer(fichiers, many=True).data,
            "manifest": ManifestSerializer(manifeste).data if manifeste else None,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_file(request, file_id):
    """
    Renvoie le bloc chiffre d'un fichier ET la DEK chiffree POUR L'APPELANT.

    Chaque ayant droit recoit sa propre copie chiffree de la meme DEK.
    Sans WrappedKey a son nom, le bloc reste inexploitable.
    """
    fichier = MedicalFile.objects.filter(id=file_id).first()

    # 404 et non 403 lorsque l'acces est illegitime : repondre 403
    # confirmerait a un attaquant que ce fichier EXISTE.
    if fichier is None or not can_access_record(request.user, fichier.patient_id):
        return Response({"detail": "Introuvable."}, status=status.HTTP_404_NOT_FOUND)

    cle = WrappedKey.objects.filter(
        file=fichier, recipient_sub=request.user.sub
    ).first()
    if cle is None:
        return Response(
            {"detail": "Aucune cle de dechiffrement pour cet utilisateur."},
            status=status.HTTP_403_FORBIDDEN,
        )

    return Response(
        {
            "id": str(fichier.id),
            "ciphertext": fichier.ciphertext,
            "iv": fichier.iv,
            "wrapped_dek": cle.wrapped_dek,
            "status": fichier.status,
        }
    )