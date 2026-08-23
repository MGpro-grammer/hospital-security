from rest_framework import serializers

from .models import UserKeys


class UserKeysSerializer(serializers.ModelSerializer):
    """
    Note importante : `keycloak_sub` est volontairement ABSENT des champs.
    L'identite de l'utilisateur provient exclusivement du jeton verifie,
    jamais du corps de la requete. Sans cela, n'importe qui pourrait
    enregistrer ou remplacer les cles de n'importe qui d'autre.
    """

    class Meta:
        model = UserKeys
        fields = ["public_key", "encrypted_private_key", "private_key_iv", "created_at"]
        read_only_fields = ["created_at"]