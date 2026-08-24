from django.contrib import admin

from .models import MedicalFile, RecordManifest, WrappedKey


@admin.register(MedicalFile)
class MedicalFileAdmin(admin.ModelAdmin):
    """
    Demonstration : l'administrateur ne voit qu'un bloc chiffre. Ni le nom
    du fichier, ni sa date d'examen, ni son contenu ne lui sont accessibles.
    """

    list_display = ("id", "patient", "status", "created_at")
    readonly_fields = ("id", "patient", "ciphertext", "iv", "uploaded_by", "created_at")


@admin.register(WrappedKey)
class WrappedKeyAdmin(admin.ModelAdmin):
    list_display = ("file", "recipient_sub", "created_at")
    readonly_fields = ("file", "recipient_sub", "wrapped_dek", "created_at")


@admin.register(RecordManifest)
class RecordManifestAdmin(admin.ModelAdmin):
    list_display = ("patient", "version", "updated_at")
    readonly_fields = ("patient", "content", "signature", "version", "updated_at")