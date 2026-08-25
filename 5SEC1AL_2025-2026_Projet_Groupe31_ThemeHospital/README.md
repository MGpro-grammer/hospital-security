# Hospital Security — Projet 5SEC1A

Système client/serveur sécurisé de gestion de dossiers médicaux, chiffré de bout en bout.

## Membres du groupe 31

| Nom | Matricule |
|---|---|
| MOURATIDIS Georges | 62218 |
| GRANDE Ian | 62265 |

---

## 1. Présentation

L'application permet à un **patient** de déposer, consulter, modifier et supprimer les fichiers de son dossier médical, et d'autoriser des **médecins** à y accéder. Un médecin autorisé peut consulter le dossier, et proposer un dépôt, une modification ou une suppression — chaque proposition exigeant l'approbation explicite du patient.

**Le serveur ne peut lire aucun contenu médical.** Chiffrement et déchiffrement ont lieu exclusivement dans le navigateur. Le serveur ne stocke que des blocs chiffrés et des clés elles-mêmes chiffrées, qu'il est incapable d'ouvrir.

L'authentification se fait **sans mot de passe**, par clé d'accès matérielle (WebAuthn), et la clé qui protège les clés privées de l'utilisateur est dérivée de cet authentificateur — elle n'est jamais stockée, ni sur le serveur, ni sur le disque.

### Composants

| Service | Rôle | Port |
|---|---|---|
| `frontend` | Vue.js 3 compilé, servi par nginx | 443 (redirection depuis 80) |
| `django` | API REST, servie par gunicorn | 8000 |
| `keycloak` | Fournisseur d'identité OpenID Connect | 8443 |
| `db` | PostgreSQL 16 | interne |

Toutes les communications sont en HTTPS, sans exception.

---

## 2. Prérequis

- **Docker Engine** et le plugin **Docker Compose v2**
- **OpenSSL**
- Un navigateur récent : **Microsoft Edge**, **Google Chrome** ou dérivé Chromium
- Un **authentificateur WebAuthn compatible avec l'extension PRF** (voir section 5)

Sous Ubuntu, `install.sh` installe Docker et OpenSSL s'ils manquent. Sous Windows, Docker Desktop doit être installé au préalable.

---

## 3. Installation

### Ubuntu 22.04 x64

```
git clone git@git.esi-bru.be:62218/security-project.git
cd <DEPOT>/5SEC1AL_2025-2026_Projet_Groupe31_ThemeHospital
chmod +x install.sh
./install.sh
```

Le script demandera le mot de passe `sudo` s'il doit installer Docker ou OpenSSL.

### Windows 10 x64

Prérequis : **Docker Desktop** installé et démarré, et **Git for Windows** (qui fournit Git Bash et OpenSSL).

Dans PowerShell :

```
git clone git@git.esi-bru.be:62218/security-project.git
cd <DEPOT>\5SEC1AL_2025-2026_Projet_Groupe31_ThemeHospital
bash install.sh
```

### Ce que fait `install.sh`

1. vérifie et installe les dépendances manquantes (Ubuntu uniquement) ;
2. crée `.env` à partir de `.env.example`, en **tirant au sort** `SECRET_KEY`, `POSTGRES_PASSWORD` et `KEYCLOAK_ADMIN_PASSWORD` ;
3. génère l'autorité de certification locale et le certificat serveur ;
4. construit les images et démarre les quatre services ;
5. applique les migrations et crée la table de cache.

Le realm Keycloak (flux d'authentification sans mot de passe, client, groupes, politique WebAuthn) est **importé automatiquement** au premier démarrage depuis `keycloak/import/hospital-realm.json`.

---

## 4. Faire confiance à l'autorité locale

**Étape obligatoire.** Sans elle, le navigateur affiche un avertissement de sécurité — et surtout, **WebAuthn refuse de fonctionner** : l'API exige un contexte sécurisé, ce qu'une connexion TLS non validée n'est pas.

Le fichier à installer est `certs/ca.crt`, généré sur votre machine à l'étape 3 de l'installation.

### Windows

Dans PowerShell, depuis le dossier du projet :

```
Import-Certificate -FilePath .\certs\ca.crt -CertStoreLocation Cert:\CurrentUser\Root
```

Confirmez la boîte de dialogue. Le magasin `CurrentUser` suffit et n'exige aucun droit administrateur — principe du moindre privilège.

### Ubuntu — magasin système

```
sudo cp certs/ca.crt /usr/local/share/ca-certificates/hospital-security-ca.crt
sudo update-ca-certificates
```

### Ubuntu — magasin de Chrome / Chromium

Chrome sous Linux n'utilise pas le magasin système mais sa propre base NSS :

```
sudo apt-get install -y libnss3-tools
certutil -d sql:$HOME/.pki/nssdb -A -t "C,," -n "Hospital Security CA" -i certs/ca.crt
```

Redémarrez complètement le navigateur après l'installation.

### Vérification

Ouvrez `https://localhost`. Le cadenas doit être fermé, sans avertissement.

---

## 5. Prérequis matériel : WebAuthn avec extension PRF

L'application dérive la clé qui protège vos clés privées depuis votre authentificateur, via l'extension **PRF** de WebAuthn (`hmac-secret`). Sans elle, l'application ne peut pas fonctionner.

**Configuration validée :**

| Élément | Valeur testée |
|---|---|
| Système | Windows 11 (build 26200) |
| Navigateur | Microsoft Edge 151 |
| Authentificateur | Windows Hello — **clé enregistrée sur l'appareil** |

**Fonctionnent également** : les clés de sécurité FIDO2 récentes (YubiKey série 5, SoloKeys) supportant `hmac-secret`, ainsi que Chrome sur Windows et sur Linux.

**Ne fonctionnent pas** : les gestionnaires de mots de passe qui interceptent la création de clé d'accès sans implémenter PRF. Au moment de créer la clé, choisissez explicitement **« Cet appareil »** (ou « This device ») plutôt qu'un gestionnaire tiers.

> Si l'application affiche `PRF indisponible sur cet authentificateur`, c'est que la clé d'accès a été créée par un composant qui ne supporte pas PRF. Supprimez-la (Paramètres Windows → Comptes → Clés d'accès, filtre `localhost`), puis réinscrivez-vous en choisissant « Cet appareil ».

---

## 6. Utilisation

L'application est sur **https://localhost**.

### Créer un patient

1. **1. Se connecter** → *Register* sur la page Keycloak
2. Renseignez un nom d'utilisateur et un courriel, puis créez la clé d'accès en choisissant **« Cet appareil »**
3. De retour dans l'application : **2. Créer mon profil**, puis **3. Enregistrer mes clés**

Le groupe `patients` est attribué **automatiquement** à l'inscription.

### Créer un médecin

Le rôle `doctors` n'est jamais auto-attribué : c'est le rôle privilégié, il est accordé par l'organisation.

1. Inscrivez un second compte comme ci-dessus ;
2. Console Keycloak (`https://localhost:8443`, identifiant `admin`, mot de passe dans `.env`) → realm **hospital** → **Users** → le compte → onglet **Groups** → **Join Group** → `doctors` ;
3. Reconnectez-vous avec ce compte, puis **2. Créer mon profil** (le champ *Organisation* apparaît) et **3. Enregistrer mes clés**.

### Parcours de démonstration

**Côté patient** — après **4. Déverrouiller mes clés** :

- déposer un fichier chiffré dans son dossier ;
- **6. Lire mon dossier** : la mention `MANIFESTE VALIDE` confirme que la liste livrée par le serveur correspond exactement à la liste signée par le patient ;
- **7. Chercher un médecin** → **Autoriser** : le navigateur re-chiffre les clés de chaque fichier pour ce médecin ;
- **Retirer** : le lien et toutes les clés du médecin sont supprimés.

**Côté médecin** :

- **7. Chercher un patient** → **Demander l'accès** : la demande reste *en attente* ;
- une fois approuvée par le patient : **Ouvrir le dossier**, puis **Ouvrir** un fichier ;
- **9. Déposer** un fichier : il arrive en `pending_approval` et **n'entre pas dans le dossier** tant que le patient ne l'a pas approuvé et contresigné ;
- **Remplacer** / **Demander la suppression** : propositions soumises à l'approbation du patient.

### Démonstration à montrer : le serveur ne voit rien

```
docker compose exec db psql -U hospital -d hospital -P pager=off -c "SELECT id, LEFT(ciphertext, 40) FROM records_medicalfile;"
```

Aucun nom de fichier, aucune date d'examen, aucun contenu : les trois sont sérialisés puis chiffrés dans un même bloc.

```
docker compose exec db psql -U hospital -d hospital -P pager=off -c "SELECT file_id, recipient_sub, LEFT(wrapped_dek, 24) FROM records_wrappedkey ORDER BY file_id;"
```

Pour un même fichier, deux enveloppes — celle du patient et celle du médecin — **sans un octet en commun**, bien qu'elles protègent la même clé. Le rembourrage aléatoire de RSA-OAEP fait que le serveur ne peut même pas déduire qu'il s'agit du même secret. Le fichier chiffré, lui, n'est stocké **qu'une fois**.

---

## 7. Transfert sécurisé de la clé publique du serveur

`health.pdf` exige un mécanisme permettant de transférer la clé publique du serveur **et d'en vérifier l'appartenance**.

### Le mécanisme

La clé publique du serveur est contenue dans son certificat X.509 (`certs/server.crt`), signé par une autorité de certification locale (`certs/ca.crt`) créée à l'installation.

**Le certificat de l'autorité est transféré hors bande.** Il est produit sur la machine qui exécute le projet et installé **manuellement** dans le magasin de confiance du système (section 4). **Il ne provient jamais du serveur par le réseau.** C'est le point essentiel : demander sa clé publique à l'entité qu'on cherche à authentifier n'apporte aucune garantie — un intermédiaire répondrait simplement avec la sienne.

### La vérification d'appartenance

À chaque connexion, le navigateur contrôle deux choses, et refuse si l'une échoue :

1. **La chaîne de signature.** Le certificat présenté par le serveur est-il signé par l'autorité installée dans le magasin de confiance ? Un attaquant qui présenterait un certificat auto-signé, ou signé par une autre autorité, serait rejeté.
2. **La correspondance du nom.** Le nom d'hôte demandé (`localhost`) figure-t-il dans le champ `subjectAltName` du certificat ? Un certificat valide mais émis pour un autre nom est rejeté — cela empêche de réutiliser un certificat légitime obtenu ailleurs.

Le champ `subjectAltName` est défini dans `certs/server.ext` et couvre `localhost`, `127.0.0.1`, `::1` ainsi que les noms de service internes.

### Le même mécanisme, à l'échelle réelle

En production, l'autorité locale serait remplacée par une autorité publique (Let's Encrypt ou commerciale), dont le certificat racine est **déjà présent** dans le magasin du système d'exploitation, installé lui aussi hors bande — au moment de l'installation du système. Le mécanisme est identique ; seule change la façon dont la confiance initiale est établie.

### Limite assumée : les clés publiques des utilisateurs

Les clés publiques RSA des utilisateurs (chiffrement et signature) sont, elles, distribuées **par l'API**. Un serveur malveillant pourrait substituer sa propre clé publique à celle d'un médecin, et lire ensuite les fichiers qu'un patient croirait partager avec lui.

Fermer complètement cette porte exigerait une vérification hors bande entre utilisateurs : comparaison d'empreintes de clé lues de vive voix, ou lecture d'un QR code en présentiel — le modèle des applications de messagerie chiffrée. **Cela dépasse le périmètre de ce projet, mais la limite est identifiée et assumée.**

---

## 8. Architecture de sécurité

### Chaîne de dérivation des clés

```
  authentificateur materiel (Windows Hello / FIDO2)
        |  extension PRF (hmac-secret)
        v
  32 octets, deterministes, JAMAIS stockes
        |  HKDF-SHA256
        v
  KEK  AES-256-GCM, NON extractible
        |  chiffre
        v
  cle privee RSA de l'utilisateur (stockee chiffree sur le serveur)
```

Le serveur détient les clés privées des utilisateurs **sous forme chiffrée** et est incapable de les déchiffrer : la clé qui les protège n'existe que le temps d'une session, dans la mémoire du navigateur.

### Chiffrement en enveloppe

```
  fichier ---[DEK AES-256-GCM]---> bloc chiffre (stocke UNE fois)
     DEK ---[RSA-OAEP, cle publique du patient]---> enveloppe 1
     DEK ---[RSA-OAEP, cle publique du medecin]---> enveloppe 2
```

Nom du fichier, date d'examen et contenu sont sérialisés puis chiffrés **ensemble**, dans un seul bloc : le serveur ne connaît même pas le nom des documents qu'il héberge.

### Manifeste signé

Le chiffrement protège chaque fichier ; il ne protège pas la **liste** des fichiers. Un serveur compromis pourrait supprimer un examen gênant ou ajouter un faux document sans que rien ne le trahisse : chaque fichier restant serait parfaitement valide.

Le dossier possède donc un **manifeste** — la liste des identifiants et un compteur de version — signé par la clé privée RSA-PSS du patient. Le client vérifie la signature, puis compare la liste signée à la liste effectivement livrée, **dans les deux sens** : une comparaison unidirectionnelle ne détecterait qu'une suppression, ou qu'un ajout, mais pas les deux.

Le compteur de version est monotone : le serveur refuse un manifeste dont la version n'augmente pas, ce qui bloque le rejeu d'un ancien manifeste valablement signé.

### Contrôle d'accès

- **Refus par défaut** : tout endpoint exige un jeton valide, sauf mention explicite.
- Le rôle est déduit du **groupe porté par le jeton signé**, jamais d'un champ envoyé par le client.
- Contrôle **objet par objet** : un médecin approuvé pour le patient A ne peut pas lire les fichiers du patient B.
- `GET /api/records/files/<uuid>` répond **404 et non 403** en cas d'accès illégitime : un 403 confirmerait à un attaquant que le fichier existe.

### Durcissement

`DEBUG=False`, gunicorn (aucun débogueur interactif), admin Django désactivé hors développement, HSTS, CSP stricte, cookies sécurisés, limitation de débit avec compteur partagé entre les workers, détection de force brute côté Keycloak, déconnexion OIDC complète.

---

## 9. Documentation développeur

Toutes les commandes se lancent depuis ce dossier.

### Back-end (Sphinx)

```
docker run --rm -v ${PWD}/backend:/app -w /app python:3.12-slim \
  sh -c "pip install -q -r requirements.txt -r requirements-docs.txt && sphinx-build -b html docs docs/_build"
```

Résultat : `backend/docs/_build/index.html`. Configuration : `backend/docs/conf.py`, `backend/docs/index.rst`.

### Front-end (JSDoc)

```
docker run --rm -v ${PWD}/frontend:/app -w /app node:22-alpine \
  sh -c "npm ci && npm run docs"
```

Variante sans installation complète, nettement plus rapide sous Windows :

```
docker run --rm -v ${PWD}/frontend:/app -w /app node:22-alpine \
  npx --yes jsdoc -c jsdoc.json
```

Résultat : `frontend/docs/index.html`. Configuration : `frontend/jsdoc.json`.

Les deux documentations sont **extraites des commentaires du code source** : elles ne peuvent pas diverger de l'implémentation.

---

## 10. Tests

### Back-end

```
docker compose exec django python manage.py test
```

### Front-end

```
docker run --rm -v ${PWD}/frontend:/app -w /app node:22-alpine \
  sh -c "npm ci && npx vitest run"
```

### Audit de configuration Django

```
docker compose exec django python manage.py check --deploy
```

Attendu : `System check identified no issues (1 silenced)`. Le contrôle écarté est `security.W021` (préchargement HSTS), sans objet pour `localhost` — la justification figure dans `backend/config/settings.py`.

### Audit des dépendances

```
docker run --rm -v ${PWD}/frontend:/app -w /app node:22-alpine npm audit

docker run --rm -v ${PWD}/backend:/app -w /app python:3.12-slim \
  sh -c "pip install pip-audit -q && pip-audit -r requirements.txt"
```

---

## 11. Exploitation

| Action | Commande |
|---|---|
| Voir l'état des services | `docker compose ps` |
| Consulter les journaux | `docker compose logs -f django` |
| Arrêter (données conservées) | `docker compose down` |
| Redémarrer | `docker compose up -d` |
| **Tout réinitialiser** | `docker compose down -v && ./install.sh` |

`docker compose down -v` supprime la base **et** les comptes Keycloak. Le realm est réimporté automatiquement au démarrage suivant ; les comptes utilisateurs, eux, sont à recréer.

> Après une réinitialisation, les anciennes clés d'accès restent enregistrées dans le système d'exploitation alors que les comptes correspondants n'existent plus. Supprimez-les avant de vous réinscrire (Paramètres Windows → Comptes → Clés d'accès, filtre `localhost`).

---

## 12. Limites assumées

| Limite | Pourquoi elle est irréductible |
|---|---|
| **Perte de clé = perte du dossier** | La clé qui protège la clé privée est dérivée de l'authentificateur et n'est stockée nulle part. Supprimer sa clé d'accès rend les dossiers illisibles **définitivement**. Ni le serveur ni un administrateur ne peuvent aider — s'ils le pouvaient, c'est qu'ils pourraient lire. |
| **Un fichier déjà téléchargé n'est pas révocable** | Retirer un médecin supprime son accès futur, pas la copie qu'il a déjà déchiffrée. Aucun système ne reprend une donnée déjà livrée. |
| **Substitution de clé publique par le serveur** | Voir section 7. Exigerait une vérification hors bande entre utilisateurs. |
| **Rémanence physique en base** | PostgreSQL ne réécrit pas immédiatement les blocs disque supprimés. Mais la suppression détruit aussi les clés : le bloc chiffré, même exhumé, ne redeviendra jamais lisible. C'est le principe du *crypto-shredding* — on ne compte pas sur l'effacement, on détruit la clé. |
| **Mémoire du navigateur** | Aucune application web ne peut garantir l'effacement de la RAM. Les clés sont des objets `CryptoKey` non extractibles, jamais placés dans `localStorage`, et le bouton **Verrouiller** en retire la seule référence utilisable. |