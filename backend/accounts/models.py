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

class Patient(models.Model):
    """
    Un patient. Son identite est stockee EN CLAIR : health.pdf ne la classe
    pas parmi les donnees sensibles (seuls le contenu, les noms et les dates
    des fichiers le sont), et un medecin doit pouvoir rechercher un patient
    pour lui demander l'acces a son dossier.
    """

    keycloak_sub = models.CharField(max_length=64, primary_key=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Patient"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Doctor(models.Model):
    """
    Un medecin. health.pdf : un utilisateur est d'UN SEUL type, et un medecin
    appartient a une seule organisation medicale.
    """

    keycloak_sub = models.CharField(max_length=64, primary_key=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    organisation = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Medecin"

    def __str__(self):
        return f"Dr {self.first_name} {self.last_name} ({self.organisation})"


class DoctorPatientLink(models.Model):
    """
    Lien entre un medecin et un patient.

    Un lien initie par le PATIENT est immediatement approuve : c'est lui qui
    decide qui accede a son dossier. Un lien initie par un MEDECIN reste en
    attente jusqu'a approbation explicite du patient.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "En attente d'approbation"
        APPROVED = "approved", "Approuve"

    class Initiator(models.TextChoices):
        PATIENT = "patient", "Patient"
        DOCTOR = "doctor", "Medecin"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="links")
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="links")
    status = models.CharField(max_length=16, choices=Status.choices)
    initiated_by = models.CharField(max_length=16, choices=Initiator.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Lien medecin-patient"
        verbose_name_plural = "Liens medecin-patient"
        constraints = [
            models.UniqueConstraint(
                fields=["patient", "doctor"], name="unique_doctor_patient_link"
            )
        ]

    def __str__(self):
        return f"{self.doctor} <-> {self.patient} ({self.status})"