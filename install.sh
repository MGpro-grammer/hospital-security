#!/usr/bin/env bash
set -e
docker compose up --build -d
echo "Environnement lancé. Frontend, backend, Keycloak et la base de données démarrent."