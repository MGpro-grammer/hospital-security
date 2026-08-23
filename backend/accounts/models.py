from django.db import models


class UserKeys(models.Model):
    """
    Cles cryptographiques d'un utilisateur.

    Le serveur stocke la cle publique en clair (c'est son role) et la cle
    privee CHIFFREE, qu'il est incapable de dechiffrer : la cle qui la
    protege est derivee dans le navigateur depuis l'authentificateur
    materiel et ne transite jamais sur le reseau.
    """

    keycloak_sub = models.CharField(
        max_length=64,
        primary_key=True,
        help_text="Identifiant stable de l'utilisateur, issu du jeton (claim sub).",
    )
    public_key = models.TextField(help_text="Cle publique RSA, format SPKI base64.")
    encrypted_private_key = models.TextField(
        help_text="Cle privee PKCS8 chiffree en AES-256-GCM, base64."
    )
    private_key_iv = models.CharField(
        max_length=32, help_text="Vecteur d'initialisation AES-GCM, base64."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cles utilisateur"
        verbose_name_plural = "Cles utilisateur"

    def __str__(self):
        return f"Cles de {self.keycloak_sub}"