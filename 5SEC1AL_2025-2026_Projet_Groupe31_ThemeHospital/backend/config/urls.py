"""
Routage racine de l'application.

L'ADMIN DJANGO N'EST DISPONIBLE QU'EN DEVELOPPEMENT.

C'est une decision de securite, pas un oubli. L'admin s'ouvre avec un
identifiant et un MOT DE PASSE classique. Or tout le projet repose sur
une authentification SANS mot de passe, adossee a un authentificateur
materiel. Laisser l'admin accessible en production reviendrait a
percer, a cote de la porte blindee, une porte ordinaire avec une simple
serrure : un attaquant n'attaquerait jamais WebAuthn, il attaquerait le
mot de passe de l'administrateur.

En developpement, l'admin reste utile pour inspecter la base et montrer
que les donnees sensibles y sont bien chiffrees. La meme demonstration
se fait desormais directement en SQL (voir le test T7.9).
"""

from django.conf import settings
from django.urls import include, path

urlpatterns = [
    path("api/", include("accounts.urls")),
    path("api/records/", include("records.urls")),
]

if settings.DEBUG:
    from django.contrib import admin

    urlpatterns += [path("admin/", admin.site.urls)]