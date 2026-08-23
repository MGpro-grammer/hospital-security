"""
Validation des jetons emis par Keycloak.

Le serveur ne stocke aucun mot de passe et n'interroge pas Keycloak a chaque
requete : il verifie la signature du jeton avec les cles publiques du serveur
d'authentification, recuperees une seule fois puis mises en cache.
"""

import jwt
from jwt import PyJWKClient
from django.conf import settings
from rest_framework import authentication, exceptions

# Recupere et met en cache les cles publiques de Keycloak.
_jwk_client = PyJWKClient(settings.KEYCLOAK_JWKS_URL, cache_keys=True)


class KeycloakUser:
    """
    Utilisateur reconstruit a partir du jeton, sans aucune ligne en base.
    Le jeton etant signe, son contenu ne peut pas etre altere par le client.
    """

    def __init__(self, claims):
        self.claims = claims
        self.sub = claims["sub"]
        self.username = claims.get("preferred_username", "")
        groups = claims.get("groups", [])
        self.is_patient = "patients" in groups
        self.is_doctor = "doctors" in groups

    @property
    def is_authenticated(self):
        return True

    def __str__(self):
        return self.username


class KeycloakAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith(self.keyword + " "):
            return None  # pas de jeton : la requete sera traitee comme anonyme

        token = header[len(self.keyword) + 1:].strip()

        try:
            signing_key = _jwk_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                # Algorithme impose. Ne JAMAIS lire l'algorithme depuis le
                # jeton lui-meme : ce serait laisser l'attaquant le choisir.
                algorithms=["RS256"],
                issuer=settings.KEYCLOAK_ISSUER,
                audience=settings.KEYCLOAK_AUDIENCE,
                options={
                    "require": ["exp", "iat", "iss", "aud", "sub"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iss": True,
                    "verify_aud": True,
                },
            )
        except jwt.PyJWTError:
            # Message volontairement generique : ne pas indiquer a un
            # attaquant laquelle des verifications a echoue.
            raise exceptions.AuthenticationFailed("Jeton invalide.")

        return (KeycloakUser(claims), token)

    def authenticate_header(self, request):
        return self.keyword