import uuid

from django.db import models

from accounts.models import Patient


class MedicalFile(models.Model):
    """
    Un fichier du dossier medical, chiffre de bout en bout.

    Le serveur ne connait NI le nom du fichier, NI sa date d'examen, NI son
    contenu : les trois sont serialises ensemble puis chiffres en UN SEUL
    bloc avec une cle de donnees (DEK) propre a ce fichier.

    L'identifiant est un UUID opaque : il ne revele ni ordre, ni date, ni
    nombre de fichiers dans le systeme.
    """

    class Status(models.TextChoices):
        APPROVED = "approved", "Approuve"
        PENDING_APPROVAL = "pending_approval", "En attente d'approbation"
        PENDING_DELETION = "pending_deletion", "Suppression en attente"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="files")
    ciphertext = models.TextField(help_text="Bloc chiffre AES-256-GCM, base64.")
    iv = models.CharField(max_length=32, help_text="Vecteur d'initialisation, base64.")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.APPROVED
    )
    uploaded_by = models.CharField(
        max_length=64, help_text="keycloak_sub de l'auteur du depot."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Fichier medical"
        verbose_name_plural = "Fichiers medicaux"
        ordering = ["created_at"]

    def __str__(self):
        return f"Fichier {self.id} ({self.status})"


class WrappedKey(models.Model):
    """
    La cle de donnees (DEK) d'un fichier, chiffree avec la cle publique RSA
    d'un ayant droit. Une ligne par couple (fichier, destinataire).

    C'est ce qui permet le partage : le patient et chacun de ses medecins
    approuves possedent leur propre copie chiffree de la MEME DEK. Le
    fichier lui-meme n'est stocke qu'une fois.
    """

    file = models.ForeignKey(
        MedicalFile, on_delete=models.CASCADE, related_name="wrapped_keys"
    )
    recipient_sub = models.CharField(
        max_length=64, help_text="keycloak_sub de l'ayant droit."
    )
    wrapped_dek = models.TextField(help_text="DEK chiffree en RSA-OAEP, base64.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cle de fichier chiffree"
        verbose_name_plural = "Cles de fichier chiffrees"
        constraints = [
            models.UniqueConstraint(
                fields=["file", "recipient_sub"], name="unique_wrapped_key_per_recipient"
            )
        ]

    def __str__(self):
        return f"DEK de {self.file_id} pour {self.recipient_sub}"


class RecordManifest(models.Model):
    """
    Manifeste signe du dossier d'un patient.

    REPOND A LA QUESTION 4 DE LA CHECK-LIST : « Does somebody have the
    ability to add or delete an item in a sequence [...] without being
    detected? »

    Le chiffrement de bout en bout protege CHAQUE fichier, pas la LISTE des
    fichiers. Sans manifeste, un serveur compromis pourrait supprimer un
    examen genant ou ajouter un faux document : chaque fichier restant
    serait parfaitement valide, seul l'ensemble aurait ete falsifie.

    Le manifeste liste les identifiants du dossier et est signe par la cle
    privee du patient (RSA-PSS). Le client verifie la signature, puis
    compare la liste signee a ce que le serveur lui a effectivement livre.
    """

    patient = models.OneToOneField(
        Patient, on_delete=models.CASCADE, related_name="manifest"
    )
    content = models.TextField(
        help_text='JSON signe : {"version": n, "files": ["uuid", ...]}'
    )
    signature = models.TextField(help_text="Signature RSA-PSS du contenu, base64.")
    version = models.PositiveIntegerField(
        default=0, help_text="Compteur monotone, refuse de reculer."
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Manifeste de dossier"
        verbose_name_plural = "Manifestes de dossier"

    def __str__(self):
        return f"Manifeste de {self.patient} (v{self.version})"