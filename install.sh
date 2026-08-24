#!/usr/bin/env bash
#
# Installation complete du projet. Idempotent : relancable sans risque.
set -e

# --- 1. Fichier de configuration --------------------------------------
#
# .env n'est PAS versionne : il contient des secrets. On le fabrique ici
# a partir de .env.example, en tirant au sort les trois valeurs
# sensibles.
#
# Pourquoi les tirer au sort plutot que de les livrer : une cle partagee
# entre deux installations n'est plus un secret. Si SECRET_KEY etait
# dans le depot, n'importe qui pourrait forger des donnees signees par
# Django sur n'importe quelle installation du projet.

alea() {
    head -c 64 /dev/urandom | base64 | LC_ALL=C tr -dc 'A-Za-z0-9' | head -c "$1"
}

if [ -f .env ]; then
    echo "[1/5] .env existe deja : conserve tel quel."
else
    echo "[1/5] Creation de .env avec des secrets aleatoires..."
    cp .env.example .env
    sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$(alea 50)|" .env
    sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(alea 32)|" .env
    sed -i "s|^KEYCLOAK_ADMIN_PASSWORD=.*|KEYCLOAK_ADMIN_PASSWORD=$(alea 32)|" .env
fi

# --- 2. Autorite de certification locale ------------------------------
echo "[2/5] Generation des certificats..."
bash certs/generate-certs.sh

# --- 3. Construction et demarrage -------------------------------------
echo "[3/5] Construction des images et demarrage des services..."
docker compose up --build -d

# --- 4. Base de donnees -----------------------------------------------
echo "[4/5] Migrations et table de cache..."
docker compose exec -T django python manage.py migrate

# Table du cache PARTAGE entre les 3 workers gunicorn. Sans elle, la
# limitation de debit echoue au premier appel.
docker compose exec -T django python manage.py createcachetable

# --- 5. Fin -----------------------------------------------------------
echo ""
echo "[5/5] Termine."
echo ""
echo "  Application : https://localhost"
echo "  Keycloak    : https://localhost:8443"
echo "                identifiant 'admin', mot de passe dans .env"
echo "                (variable KEYCLOAK_ADMIN_PASSWORD)"
echo ""
echo "IMPORTANT : installez certs/ca.crt dans le magasin de certificats de"
echo "confiance de votre systeme. Sans cela le navigateur affichera un"
echo "avertissement, et WebAuthn REFUSERA de fonctionner."