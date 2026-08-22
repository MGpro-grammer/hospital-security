#!/usr/bin/env bash
set -e
bash certs/generate-certs.sh
docker compose up --build -d
echo ""
echo "Environnement lance. Application disponible sur https://localhost"
echo "IMPORTANT : installez certs/ca.crt dans le magasin de certificats de confiance"
echo "de votre systeme, sinon le navigateur affichera un avertissement de securite."