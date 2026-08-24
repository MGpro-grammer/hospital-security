"""
Limitation de debit, adaptee a un utilisateur issu d'un jeton.
"""

from rest_framework.throttling import SimpleRateThrottle


class SubRateThrottle(SimpleRateThrottle):
    """
    Limite par UTILISATEUR, identifie par le claim `sub` du jeton.

    La classe `UserRateThrottle` fournie par DRF identifie l'utilisateur
    par `request.user.pk`. Notre utilisateur est reconstruit depuis un
    jeton verifie et n'existe PAS en base : il n'a pas de cle primaire.

    On utilise donc `sub`, l'identifiant stable et signe par Keycloak.
    Un utilisateur ne peut pas se dedoubler pour doubler son quota : il
    lui faudrait un second jeton, donc un second compte.
    """

    scope = "user"

    def get_cache_key(self, request, view):
        sub = getattr(request.user, "sub", None)
        # Sans jeton exploitable, on retombe sur l'adresse IP.
        ident = sub if sub else self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class UploadRateThrottle(SubRateThrottle):
    """
    Limite specifique au depot de fichiers.

    Un depot coute cher : un bloc chiffre et plusieurs cles ecrits en
    base, dans une transaction. Sans limite propre, un compte compromis
    saturerait le disque du serveur bien avant d'atteindre la limite
    generale. C'est un deni de service par epuisement de ressource.
    """

    scope = "upload"