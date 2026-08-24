from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import DoctorPatientLink

from .models import MedicalFile, RecordManifest, WrappedKey
from .serializers import (
    FileUploadSerializer,
    ManifestSerializer,
    ManifestUpdateSerializer,
    MedicalFileSerializer,
)
from accounts.permissions import IsDoctor, IsPatient
from accounts.throttling import UploadRateThrottle


def can_access_record(user, patient_sub):
    """
    CONTROLE D'ACCES OBJET PAR OBJET.

    Un patient n'accede qu'a SON PROPRE dossier. Un medecin n'accede a un
    dossier que si un lien APPROUVE existe. Toute autre situation : refus.

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
@throttle_classes([UploadRateThrottle])
def upload_file(request):
    """
    Depose un fichier chiffre dans un dossier medical.

    Depot par le PATIENT   -> approuve immediatement, manifeste mis a jour.
    Depot par un MEDECIN   -> en attente d'approbation, manifeste inchange.
    """
    serializer = FileUploadSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    patient_sub = data["patient_sub"]

    if not can_access_record(request.user, patient_sub):
        return Response({"detail": "Acces refuse."}, status=status.HTTP_403_FORBIDDEN)

    # L'identifiant est genere par le client : il doit figurer dans le
    # manifeste signe avant l'envoi. Le serveur en verifie l'unicite.
    if MedicalFile.objects.filter(id=data["file_id"]).exists():
        return Response(
            {"detail": "Identifiant de fichier deja utilise."},
            status=status.HTTP_409_CONFLICT,
        )

    # Une EDITION ne peut remplacer qu'un fichier du MEME dossier.
    #
    # Sans ce controle, un medecin autorise par deux patients pourrait
    # deposer chez le patient A un fichier declarant remplacer un fichier
    # du patient B. A l'approbation par A, le serveur supprimerait un
    # document du dossier de B, qui n'a rien demande et n'a rien approuve.
    #
    # Une cle etrangere garantit que la cible EXISTE, jamais qu'elle
    # appartient au bon dossier : c'est une regle metier, elle se verifie ici.
    remplace = data.get("replaces")
    if remplace and not MedicalFile.objects.filter(
        id=remplace, patient_id=patient_sub
    ).exists():
        return Response(
            {"detail": "Le fichier a remplacer n'appartient pas a ce dossier."},
            status=status.HTTP_400_BAD_REQUEST,
        )

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
            id=data["file_id"],
            patient_id=patient_sub,
            ciphertext=data["ciphertext"],
            iv=data["iv"],
            status=(
                MedicalFile.Status.APPROVED
                if est_patient
                else MedicalFile.Status.PENDING_APPROVAL
            ),
            uploaded_by=request.user.sub,
            replaces_id=data.get("replaces"),
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

def _appliquer_manifeste(patient_sub, data):
    """
    Enregistre le nouveau manifeste signe par le patient.

    Le compteur de version est MONOTONE : il refuse de reculer. C'est ce
    qui empeche un attaquant muni d'un jeton vole de rejouer un ancien
    manifeste pour faire "disparaitre" un fichier recent.

    @return: une Response d'erreur, ou None si tout s'est bien passe.
    """
    actuel = RecordManifest.objects.filter(patient_id=patient_sub).first()
    if actuel and data["manifest_version"] <= actuel.version:
        return Response(
            {"detail": "Version de manifeste obsolete."},
            status=status.HTTP_409_CONFLICT,
        )

    RecordManifest.objects.update_or_create(
        patient_id=patient_sub,
        defaults={
            "content": data["manifest_content"],
            "signature": data["manifest_signature"],
            "version": data["manifest_version"],
        },
    )
    return None


def _fichier_du_patient(file_id, patient_sub):
    """Retrouve un fichier appartenant AU patient appelant, ou None."""
    return MedicalFile.objects.filter(id=file_id, patient_id=patient_sub).first()


@api_view(["POST"])
@permission_classes([IsPatient])
def approve_file(request, file_id):
    """
    Le patient approuve un fichier depose par un medecin.

    C'est ici que le fichier ENTRE reellement dans le dossier : il passe en
    `approved` ET rejoint le manifeste signe, dans la MEME transaction. Les
    deux sont indissociables : approuver sans signer laisserait un fichier
    hors manifeste, que la verification cote client signalerait comme un
    ajout frauduleux du serveur.

    Si le fichier en remplace un autre (edition), l'ancien est supprime a
    ce moment precis, et pas avant : jusqu'a l'approbation, le patient
    conserve la version d'origine.
    """
    fichier = _fichier_du_patient(file_id, request.user.sub)
    if fichier is None:
        return Response({"detail": "Introuvable."}, status=status.HTTP_404_NOT_FOUND)
    if fichier.status != MedicalFile.Status.PENDING_APPROVAL:
        return Response(
            {"detail": "Ce fichier n'est pas en attente d'approbation."},
            status=status.HTTP_409_CONFLICT,
        )

    serializer = ManifestUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    with transaction.atomic():
        erreur = _appliquer_manifeste(request.user.sub, data)
        if erreur:
            return erreur

        fichier.status = MedicalFile.Status.APPROVED
        fichier.save(update_fields=["status"])

        # Cles rechiffrees par le patient pour ses AUTRES medecins approuves.
        # Le medecin auteur du depot a deja la sienne : il l'a fabriquee.
        WrappedKey.objects.bulk_create(
            [
                WrappedKey(
                    file=fichier,
                    recipient_sub=cle["recipient_sub"],
                    wrapped_dek=cle["wrapped_dek"],
                )
                for cle in data.get("wrapped_keys", [])
            ],
            ignore_conflicts=True,
        )

        # Defense en profondeur : meme si un fichier avait ete depose avec
        # un `replaces` frauduleux avant le controle a l'upload, on ne
        # supprime JAMAIS un fichier qui n'est pas dans le dossier de
        # l'appelant. Deux barrieres valent mieux qu'une.
        ancien = fichier.replaces
        if ancien is not None and ancien.patient_id == request.user.sub:
            ancien.delete()

    return Response({"id": str(fichier.id), "status": fichier.status})


@api_view(["POST"])
@permission_classes([IsPatient])
def reject_file(request, file_id):
    """
    Le patient refuse un fichier depose par un medecin.

    Aucun manifeste n'est requis : le fichier n'y a JAMAIS figure. Il n'a
    donc jamais fait partie du dossier, et le refuser ne change rien a la
    liste signee.
    """
    fichier = _fichier_du_patient(file_id, request.user.sub)
    if fichier is None:
        return Response({"detail": "Introuvable."}, status=status.HTTP_404_NOT_FOUND)
    if fichier.status != MedicalFile.Status.PENDING_APPROVAL:
        return Response(
            {"detail": "Ce fichier n'est pas en attente d'approbation."},
            status=status.HTTP_409_CONFLICT,
        )

    fichier.delete()
    return Response({"detail": "Depot refuse et supprime."})


@api_view(["POST"])
@permission_classes([IsDoctor])
def request_deletion(request, file_id):
    """
    Un medecin approuve DEMANDE la suppression d'un fichier.

    Il ne supprime rien. Le fichier reste dans le dossier et dans le
    manifeste : seul son statut change, pour signaler la demande au
    patient. Un medecin ne peut pas faire disparaitre une piece du dossier
    d'un patient de sa propre initiative.
    """
    fichier = MedicalFile.objects.filter(id=file_id).first()
    if fichier is None or not can_access_record(request.user, fichier.patient_id):
        return Response({"detail": "Introuvable."}, status=status.HTTP_404_NOT_FOUND)
    if fichier.status != MedicalFile.Status.APPROVED:
        return Response(
            {"detail": "Seul un fichier approuve peut faire l'objet d'une demande."},
            status=status.HTTP_409_CONFLICT,
        )

    fichier.status = MedicalFile.Status.PENDING_DELETION
    fichier.save(update_fields=["status"])
    return Response({"id": str(fichier.id), "status": fichier.status})

@api_view(["POST"])
@permission_classes([IsPatient])
def keep_file(request, file_id):
    """
    Le patient REFUSE une demande de suppression : le fichier reste.

    Sans cette route, un medecin pourrait apposer une marque indelebile
    sur le dossier d'autrui : le fichier resterait `pending_deletion` a
    jamais, sans que le patient ne puisse revenir en arriere.

    Aucun manifeste n'est requis : le fichier n'a jamais quitte la liste
    signee, seul son statut d'affichage change.
    """
    fichier = _fichier_du_patient(file_id, request.user.sub)
    if fichier is None:
        return Response({"detail": "Introuvable."}, status=status.HTTP_404_NOT_FOUND)
    if fichier.status != MedicalFile.Status.PENDING_DELETION:
        return Response(
            {"detail": "Aucune demande de suppression en cours."},
            status=status.HTTP_409_CONFLICT,
        )

    fichier.status = MedicalFile.Status.APPROVED
    fichier.save(update_fields=["status"])
    return Response({"id": str(fichier.id), "status": fichier.status})

@api_view(["DELETE"])
@permission_classes([IsPatient])
def delete_file(request, file_id):
    """
    Le patient supprime un fichier de son dossier.

    UN SEUL point de sortie, que la demande vienne d'un medecin
    (`pending_deletion`) ou du patient lui-meme (`approved`) : supprimer,
    c'est supprimer, et seul le patient execute. Deux endpoints distincts
    auraient double la surface a securiser pour un comportement identique.

    La suppression est REELLE : `delete()` retire la ligne, et les
    `WrappedKey` associees tombent en cascade. Sans les cles, le bloc
    chiffre serait de toute facon definitivement illisible.
    """
    fichier = _fichier_du_patient(file_id, request.user.sub)
    if fichier is None:
        return Response({"detail": "Introuvable."}, status=status.HTTP_404_NOT_FOUND)

    serializer = ManifestUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    with transaction.atomic():
        erreur = _appliquer_manifeste(request.user.sub, serializer.validated_data)
        if erreur:
            return erreur
        fichier.delete()

    return Response({"detail": "Fichier supprime."})