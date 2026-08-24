"""
Tests du controle d'acces sur les fichiers medicaux.
"""

import datetime

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Doctor, DoctorPatientLink, Patient

from . import views
from .models import MedicalFile

NOUVEAU = "11111111-1111-1111-1111-111111111111"


class FauxUtilisateur:
    """
    Imite l'utilisateur reconstruit depuis un jeton verifie.

    Les tests n'ont pas a fabriquer de vrais jetons Keycloak : ce qui est
    teste ici est la LOGIQUE METIER, pas la validation de signature (deja
    couverte par les tests 401 et par Keycloak lui-meme).
    """

    def __init__(self, sub, is_patient=False, is_doctor=False):
        self.sub = sub
        self.username = sub
        self.is_patient = is_patient
        self.is_doctor = is_doctor
        self.is_authenticated = True


class EditionCroiseeTest(TestCase):
    """
    Un medecin autorise par DEUX patients ne doit pas pouvoir deposer chez
    l'un un fichier declarant remplacer un fichier de l'autre.

    Sans ce controle, l'approbation par le premier patient supprimerait un
    document du dossier du second, qui n'a rien demande ni approuve.
    """

    def setUp(self):
        self.factory = APIRequestFactory()

        self.alice = Patient.objects.create(
            keycloak_sub="sub-alice",
            first_name="Alice",
            last_name="Martin",
            date_of_birth=datetime.date(1990, 1, 1),
        )
        self.bob = Patient.objects.create(
            keycloak_sub="sub-bob",
            first_name="Bob",
            last_name="Durand",
            date_of_birth=datetime.date(1985, 6, 15),
        )
        self.medecin = Doctor.objects.create(
            keycloak_sub="sub-medecin",
            first_name="Paul",
            last_name="Leclercq",
            organisation="Hopital Saint-Luc",
        )

        # Le medecin est approuve par les DEUX patients : c'est la
        # situation qui rend l'attaque possible.
        for patient in (self.alice, self.bob):
            DoctorPatientLink.objects.create(
                patient=patient,
                doctor=self.medecin,
                status=DoctorPatientLink.Status.APPROVED,
                initiated_by=DoctorPatientLink.Initiator.PATIENT,
            )

        self.fichier_de_bob = MedicalFile.objects.create(
            patient=self.bob,
            ciphertext="AA==",
            iv="AA==",
            status=MedicalFile.Status.APPROVED,
            uploaded_by="sub-bob",
        )

    def _deposer_chez_alice(self, replaces):
        request = self.factory.post(
            "/api/records/files",
            {
                "file_id": NOUVEAU,
                "patient_sub": "sub-alice",
                "ciphertext": "AA==",
                "iv": "AA==",
                "wrapped_keys": [],
                "replaces": str(replaces),
            },
            format="json",
        )
        force_authenticate(
            request, user=FauxUtilisateur("sub-medecin", is_doctor=True)
        )
        return views.upload_file(request)

    def test_remplacer_le_fichier_d_un_autre_patient_est_refuse(self):
        reponse = self._deposer_chez_alice(self.fichier_de_bob.id)

        self.assertEqual(reponse.status_code, 400)
        # Le depot frauduleux n'existe pas...
        self.assertFalse(MedicalFile.objects.filter(id=NOUVEAU).exists())
        # ...et le fichier de Bob est intact.
        self.assertTrue(
            MedicalFile.objects.filter(id=self.fichier_de_bob.id).exists()
        )

    def test_remplacer_un_fichier_du_meme_dossier_est_accepte(self):
        """Contre-epreuve : le cas legitime doit continuer de fonctionner."""
        fichier_d_alice = MedicalFile.objects.create(
            patient=self.alice,
            ciphertext="AA==",
            iv="AA==",
            status=MedicalFile.Status.APPROVED,
            uploaded_by="sub-alice",
        )

        reponse = self._deposer_chez_alice(fichier_d_alice.id)

        self.assertEqual(reponse.status_code, 201)
        depose = MedicalFile.objects.get(id=NOUVEAU)
        self.assertEqual(depose.status, MedicalFile.Status.PENDING_APPROVAL)
        self.assertEqual(depose.replaces_id, fichier_d_alice.id)