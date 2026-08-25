#!/usr/bin/env bash
#
# Installation complete du projet Hospital Security.
# Idempotent : relancable sans risque.
set -e

SUDO=""
if [ "$(id -u)" -ne 0 ]; then SUDO="sudo"; fi

installer_docker_ubuntu() {
    echo "  Installation de Docker Engine depuis le depot OFFICIEL Docker..."
    $SUDO apt-get update
    $SUDO apt-get install -y ca-certificates curl gnupg
    $SUDO install -m 0755 -d /etc/apt/keyrings

    # On enregistre la cle GPG du depot officiel : apt verifiera la
    # SIGNATURE de chaque paquet installe.
    #
    # On n'execute JAMAIS un script telecharge ("curl ... | sh") : ce
    # serait accorder les droits root a un contenu distant non verifie.
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | $SUDO gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    $SUDO chmod a+r /etc/apt/keyrings/docker.gpg

    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        | $SUDO tee /etc/apt/sources.list.d/docker.list > /dev/null

    $SUDO apt-get update
    $SUDO apt-get install -y docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin
}

# --- 0. Dependances ---------------------------------------------------
echo "[0/5] Verification des dependances..."

if ! command -v openssl > /dev/null 2>&1; then
    if command -v apt-get > /dev/null 2>&1; then
        echo "  openssl manquant : installation..."
        $SUDO apt-get update
        $SUDO apt-get install -y openssl
    else
        echo "  ERREUR : openssl est requis. Installez-le puis relancez." >&2
        exit 1
    fi
fi

if ! command -v docker > /dev/null 2>&1; then
    if [ -f /etc/os-release ] && grep -qiE 'ubuntu|debian' /etc/os-release; then
        installer_docker_ubuntu
    else
        echo "  ERREUR : Docker est requis mais absent." >&2
        echo "  Sous Windows ou macOS, installez Docker Desktop :" >&2
        echo "  https://docs.docker.com/get-docker/" >&2
        exit 1
    fi
fi

if ! docker compose version > /dev/null 2>&1; then
    echo "  ERREUR : le plugin 'docker compose' (v2) est requis." >&2
    exit 1
fi

# --- Acces au demon Docker --------------------------------------------
#
# Sur une installation neuve, /var/run/docker.sock appartient au groupe
# `docker` et l'utilisateur courant n'y est pas encore. Or l'appartenance
# a un groupe n'est prise en compte qu'a la PROCHAINE ouverture de
# session : l'ajouter ne debloque pas le script en cours.
#
# On fait donc les deux :
#   - ajout au groupe, pour les commandes futures de l'utilisateur ;
#   - prefixe sudo pour CE script, si le socket n'est pas joignable.
#
# A savoir : appartenir au groupe `docker` equivaut a un acces root sur
# la machine (on peut monter n'importe quel repertoire de l'hote dans un
# conteneur privilegie). C'est une commodite de developpement, pas une
# configuration de production.

DOCKER="docker"
if ! docker info > /dev/null 2>&1; then
    $SUDO groupadd -f docker
    $SUDO usermod -aG docker "$USER"
    DOCKER="$SUDO docker"
    echo "  Utilisateur '$USER' ajoute au groupe 'docker'."
    echo "  Cette execution passe par sudo ; rouvrez votre session pour"
    echo "  utiliser 'docker' sans sudo par la suite."
fi

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
$DOCKER compose up --build -d

# --- 4. Base de donnees -----------------------------------------------
echo "[4/5] Migrations et table de cache..."
$DOCKER compose exec -T django python manage.py migrate

# Table du cache PARTAGE entre les 3 workers gunicorn. Sans elle, la
# limitation de debit echoue au premier appel.
$DOCKER compose exec -T django python manage.py createcachetable

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
echo "La procedure exacte est dans le README, section \"Faire confiance a"
echo "l'autorite locale\"."