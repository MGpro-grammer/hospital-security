"""
Configuration Sphinx pour la documentation developpeur du back-end.

Sphinx lit les DOCSTRINGS du code (extension `autodoc`) : la
documentation ne peut donc pas diverger de l'implementation, puisqu'elle
en est extraite.

Django doit etre initialise AVANT tout import de module applicatif :
importer un modele sans `django.setup()` leve `ImproperlyConfigured`.

Les variables d'environnement ci-dessous sont FACTICES et le restent :
generer la documentation ne se connecte a aucune base de donnees, ne
contacte aucun serveur, et n'utilise aucun secret reel.
"""

import os
import sys
from pathlib import Path

import django

# La racine du projet Django, pour que `import accounts` fonctionne.
RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

# `settings.py` refuse de demarrer si une variable manque -- c'est
# voulu. On fournit donc des valeurs de facade, jamais utilisees.
os.environ.setdefault("SECRET_KEY", "documentation-uniquement-non-secret")
os.environ.setdefault("DEBUG", "False")
os.environ.setdefault("POSTGRES_DB", "doc")
os.environ.setdefault("POSTGRES_USER", "doc")
os.environ.setdefault("POSTGRES_PASSWORD", "doc")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("KEYCLOAK_ISSUER", "https://localhost:8443/realms/hospital")
os.environ.setdefault(
    "KEYCLOAK_JWKS_URL",
    "https://localhost:8443/realms/hospital/protocol/openid-connect/certs",
)
os.environ.setdefault("KEYCLOAK_AUDIENCE", "hospital-backend")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "https://localhost")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django.setup()

# --- Identification du projet -----------------------------------------

project = "Hospital Security - Back-end"
author = "Groupe 31 - Mouratidis Georges (62218), Grande Ian (62265)"
release = "1.0"
language = "fr"

# --- Extensions --------------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",   # extrait les docstrings des modules
    "sphinx.ext.napoleon",  # comprend les docstrings de style Google
    "sphinx.ext.viewcode",  # ajoute un lien vers le code source
]

exclude_patterns = ["_build"]
html_theme = "alabaster"