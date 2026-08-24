from rest_framework import serializers

from .models import Doctor, DoctorPatientLink, Patient, UserKeys

class UserKeysSerializer(serializers.ModelSerializer):
    """
    Note importante : `keycloak_sub` est volontairement ABSENT des champs.
    L'identite de l'utilisateur provient exclusivement du jeton verifie,
    jamais du corps de la requete. Sans cela, n'importe qui pourrait
    enregistrer ou remplacer les cles de n'importe qui d'autre.
    """

    class Meta:
        model = UserKeys
        fields = [
            "public_key",
            "encrypted_private_key",
            "private_key_iv",
            "signing_public_key",
            "encrypted_signing_private_key",
            "signing_private_key_iv",
            "created_at",
        ]
        read_only_fields = ["created_at"]

class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ["keycloak_sub", "first_name", "last_name", "date_of_birth"]
        read_only_fields = ["keycloak_sub"]


class DoctorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Doctor
        fields = ["keycloak_sub", "first_name", "last_name", "organisation"]
        read_only_fields = ["keycloak_sub"]

class DoctorPublicSerializer(serializers.ModelSerializer):
    """
    Vue publique d'un medecin, incluant sa cle publique de chiffrement.

    C'est avec cette cle que le patient rechiffrera les DEK de ses fichiers.
    Une cle PUBLIQUE n'est pas un secret : la diffuser est son role meme.
    """

    public_key = serializers.SerializerMethodField()

    class Meta:
        model = Doctor
        fields = [
            "keycloak_sub",
            "first_name",
            "last_name",
            "organisation",
            "public_key",
        ]

    def get_public_key(self, obj):
        cles = UserKeys.objects.filter(keycloak_sub=obj.keycloak_sub).first()
        return cles.public_key if cles else None

class PatientPublicSerializer(serializers.ModelSerializer):
    """
    Vue publique d'un patient, destinee a la recherche par un medecin.

    Volontairement MINIMALE : ni date de naissance, ni cle publique. Un
    medecin qui cherche un patient pour lui DEMANDER l'acces n'a besoin
    que de l'identifier. Tout champ supplementaire serait une fuite
    d'information gratuite, avant meme tout consentement.
    """

    class Meta:
        model = Patient
        fields = ["keycloak_sub", "first_name", "last_name"]

class LinkSerializer(serializers.ModelSerializer):
    """Lien medecin-patient, avec les noms et les cles PUBLIQUES des deux parties."""

    doctor_name = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()
    doctor_public_key = serializers.SerializerMethodField()
    patient_signing_public_key = serializers.SerializerMethodField()

    class Meta:
        model = DoctorPatientLink
        fields = [
            "id",
            "patient_id",
            "doctor_id",
            "doctor_name",
            "patient_name",
            "doctor_public_key",
            "patient_signing_public_key",
            "status",
            "initiated_by",
            "created_at",
            "approved_at",
        ]

    def get_doctor_name(self, obj):
        return f"Dr {obj.doctor.first_name} {obj.doctor.last_name} ({obj.doctor.organisation})"

    def get_patient_name(self, obj):
        return f"{obj.patient.first_name} {obj.patient.last_name}"

    def get_doctor_public_key(self, obj):
        """Cle de CHIFFREMENT du medecin : le patient s'en sert pour re-sceller ses DEK."""
        cles = UserKeys.objects.filter(keycloak_sub=obj.doctor_id).first()
        return cles.public_key if cles else None

    def get_patient_signing_public_key(self, obj):
        """Cle de SIGNATURE du patient : le medecin s'en sert pour verifier le manifeste."""
        cles = UserKeys.objects.filter(keycloak_sub=obj.patient_id).first()
        return cles.signing_public_key if cles else None