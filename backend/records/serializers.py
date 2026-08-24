from rest_framework import serializers

from .models import MedicalFile, RecordManifest


class WrappedKeyInputSerializer(serializers.Serializer):
    """Une DEK chiffree pour un ayant droit, envoyee a l'upload."""

    recipient_sub = serializers.CharField(max_length=64)
    wrapped_dek = serializers.CharField()


class FileUploadSerializer(serializers.Serializer):
    """
    Corps d'une requete d'upload.

    Le manifeste accompagne le fichier : un depot par le patient met a jour
    la liste signee dans la MEME transaction. Un fichier ne peut donc pas
    exister hors du manifeste.
    """
    file_id = serializers.UUIDField()
    patient_sub = serializers.CharField(max_length=64)
    ciphertext = serializers.CharField()
    iv = serializers.CharField(max_length=32)
    wrapped_keys = WrappedKeyInputSerializer(many=True)
    manifest_content = serializers.CharField(required=False, allow_blank=True)
    manifest_signature = serializers.CharField(required=False, allow_blank=True)
    manifest_version = serializers.IntegerField(required=False)


class MedicalFileSerializer(serializers.ModelSerializer):
    """
    Metadonnees seules : PAS de ciphertext. Lister un dossier ne doit pas
    telecharger tous les fichiers.
    """

    class Meta:
        model = MedicalFile
        fields = ["id", "status", "uploaded_by", "created_at"]


class ManifestSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecordManifest
        fields = ["content", "signature", "version", "updated_at"]