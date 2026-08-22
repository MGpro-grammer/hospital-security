#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# Git Bash (MSYS2) convertit tout argument commencant par "/" en chemin Windows.
# Sans cette ligne, "-subj /C=BE/..." devient "C:/Program Files/Git/C=BE/...".
# Cette variable n'existe pas sous Linux : elle y est simplement ignoree.
export MSYS_NO_PATHCONV=1

if [ -f server.crt ]; then
  echo "Certificats deja presents, generation ignoree."
  exit 0
fi

echo "1/3 Creation de l'autorite de certification locale..."
openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
  -keyout ca.key -out ca.crt \
  -subj "/C=BE/O=Hospital Security Groupe 31/CN=Hospital Security Local CA"

echo "2/3 Creation de la demande de certificat serveur..."
openssl req -newkey rsa:2048 -nodes \
  -keyout server.key -out server.csr \
  -subj "/C=BE/O=Hospital Security Groupe 31/CN=localhost"

echo "3/3 Signature du certificat serveur par l'autorite..."
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out server.crt -days 398 -sha256 \
  -extfile server.ext

rm -f server.csr
chmod 644 server.crt ca.crt server.key

echo ""
echo "Termine. Installez ca.crt dans le magasin de certificats de confiance."