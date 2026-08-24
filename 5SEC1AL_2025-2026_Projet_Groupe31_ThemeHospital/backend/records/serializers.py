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
    replaces = serializers.UUIDField(required=False, allow_null=True)
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
        fields = ["id", "status", "uploaded_by", "replaces", "created_at"]


class ManifestSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecordManifest
        fields = ["content", "signature", "version", "updated_at"]

class ManifestUpdateSerializer(serializers.Serializer):
    """
    Corps d'une requete qui MODIFIE la liste des fichiers approuves.

    Toute modification de cette liste impose un manifeste neuf, signe par
    le patient. Sans cela, la liste signee et la realite divergeraient, et
    la verification cote client leverait une alerte a la lecture suivante.
    """

    manifest_content = serializers.CharField()
    manifest_signature = serializers.CharField()
    manifest_version = serializers.IntegerField()
    wrapped_keys = WrappedKeyInputSerializer(many=True, required=False)