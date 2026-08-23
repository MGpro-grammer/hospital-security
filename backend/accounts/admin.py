from django.contrib import admin

from .models import Doctor, DoctorPatientLink, Patient, UserKeys

admin.site.register(Patient)
admin.site.register(Doctor)
admin.site.register(DoctorPatientLink)


@admin.register(UserKeys)
class UserKeysAdmin(admin.ModelAdmin):
    """
    Enregistre dans l'administration a des fins de DEMONSTRATION.

    Un administrateur y voit la cle privee CHIFFREE et rien d'autre. Il ne
    peut pas la dechiffrer : la cle qui la protege n'existe que dans le
    navigateur du patient, derivee de son authentificateur materiel.

    Tous les champs sont en lecture seule : l'administration ne doit pas
    permettre d'alterer des donnees cryptographiques.
    """

    list_display = ("keycloak_sub", "created_at")
    readonly_fields = (
        "keycloak_sub",
        "public_key",
        "encrypted_private_key",
        "private_key_iv",
        "signing_public_key",
        "encrypted_signing_private_key",
        "signing_private_key_iv",
        "created_at",
    )