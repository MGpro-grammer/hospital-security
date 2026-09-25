<div align="center">

# Hospital Security

**End-to-end encrypted medical records platform — passwordless sign-in with WebAuthn, encryption keys derived from the user's authenticator, and a server that cannot read a single byte of medical data.**

![Vue.js](https://img.shields.io/badge/Vue.js-3-4FC08D?style=flat&logo=vuedotjs&logoColor=white)
![Django](https://img.shields.io/badge/Django-6.1-092E20?style=flat&logo=django&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)
![Keycloak](https://img.shields.io/badge/Keycloak-26-4D4D4D?style=flat&logo=keycloak&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat&logo=postgresql&logoColor=white)
![nginx](https://img.shields.io/badge/nginx-009639?style=flat&logo=nginx&logoColor=white)
![Docker Compose](https://img.shields.io/badge/Docker_Compose-2496ED?style=flat&logo=docker&logoColor=white)
![WebAuthn](https://img.shields.io/badge/WebAuthn-PRF-3423A6?style=flat&logo=webauthn&logoColor=white)
![Web Crypto API](https://img.shields.io/badge/Web_Crypto_API-555555?style=flat)
![Vitest](https://img.shields.io/badge/Vitest-tested-6E9F18?style=flat&logo=vitest&logoColor=white)

</div>

> [!NOTE]
> This README is being rewritten. Installation and usage instructions are currently available in
> [`5SEC1AL_2025-2026_Projet_Groupe31_ThemeHospital/README.md`](5SEC1AL_2025-2026_Projet_Groupe31_ThemeHospital/README.md).


## About

**Hospital Security** is a client/server application for managing medical records. A **patient** uploads,
views, updates and deletes the files of their medical record, and decides which **doctors** may access it.
An authorised doctor can read the record and propose to add, replace or delete a file — every proposal
requires the patient's explicit approval.

**The server cannot read any medical content.** All encryption and decryption happen in the browser: the
server only stores encrypted blobs and keys that are themselves encrypted, which it has no way to open.
Even file names and exam dates are encrypted together with the content.

Sign-in is **passwordless**, with WebAuthn passkeys. The key that protects each user's private keys is
derived from their authenticator through the WebAuthn **PRF** extension: it is never stored, neither on the
server nor on disk.

> **Context** — Academic team project carried out at HE2B ESI (Brussels) by **Georges Mouratidis** and
> **Ian Grande** for the Security course (2025-2026), with a strong focus on end-to-end encryption,
> passwordless authentication and a documented threat model.


## Features

- **Passwordless authentication** — sign-up and sign-in with WebAuthn passkeys (Windows Hello, FIDO2 security
  keys) through Keycloak and OpenID Connect. The patient role is assigned automatically; the doctor role can
  only be granted by the organisation.
- **Client-side end-to-end encryption** — every file is encrypted in the browser with its own AES-256-GCM key
  before being uploaded. File name, exam date and content are encrypted together in a single blob.
- **Keys bound to the authenticator** — the key that protects each user's private keys is derived from their
  authenticator (WebAuthn PRF + HKDF-SHA256). It is non-extractable and never stored anywhere.
- **Medical record management** — the patient uploads, views, replaces and deletes the files of their record.
- **Consent-based sharing** — the patient authorises or revokes doctors. When access is granted, the browser
  re-encrypts each file key for the doctor (RSA-OAEP); the file itself is stored only once.
- **Doctor proposals under patient control** — an authorised doctor can propose to add, replace or delete a
  file. Nothing enters the record until the patient approves and countersigns it.
- **Tamper-evident record** — a manifest signed by the patient (RSA-PSS) detects any file removed or added by
  the server, and a monotonic version counter prevents the replay of an older manifest.
- **Hardened deployment** — HTTPS everywhere through a local certificate authority, strict CSP, HSTS, rate
  limiting, brute-force detection in Keycloak, and a one-command installation that generates random secrets.


## Tech stack

| Area             | Technology                                                                          |
|------------------|-------------------------------------------------------------------------------------|
| Frontend         | Vue.js 3 (Options API), Vite — served by nginx                   |
| Cryptography     | Web Crypto API — AES-256-GCM, RSA-OAEP, RSA-PSS, HKDF-SHA256                        |
| Authentication   | Keycloak 26 (OpenID Connect), WebAuthn passkeys with the PRF extension              |
| Backend          | Python 3.12, Django 6.1, Django REST Framework, Gunicorn                            |
| Token validation | PyJWT — JWT signatures checked against Keycloak's public keys (JWKS)                |
| Database         | PostgreSQL 16                                                                       |
| Infrastructure   | Docker Compose, local certificate authority generated with OpenSSL                  |
| Documentation    | Sphinx (backend), JSDoc (frontend)                                                  |
| Tests            | Django test runner, Vitest, Vue Test Utils                                          |


## Architecture

The application runs as four Docker Compose services. The browser is the only place where medical data
exists in plaintext: it encrypts and decrypts everything locally and only exchanges ciphertext with the server.

![Service architecture: the browser talks over HTTPS to nginx, Keycloak and the Django API; Django checks token signatures with Keycloak's public keys and stores only ciphertext in PostgreSQL](docs/images/architecture.svg)

| Service    | Role                                                        | Port                      |
|------------|-------------------------------------------------------------|---------------------------|
| `frontend` | Compiled Vue.js 3 app served by nginx, with security headers | 443 (80 redirects to 443) |
| `django`   | REST API served by Gunicorn, which terminates TLS itself    | 8000                      |
| `keycloak` | OpenID Connect identity provider, passwordless flow         | 8443                      |
| `db`       | PostgreSQL 16, reachable only from the internal network     | —                         |

All communications use HTTPS, without exception. The Keycloak realm (passwordless flow, client, groups and
WebAuthn policy) is imported automatically at first startup.


## Security design

### Key derivation

Sign-in is passwordless, and so is the protection of the keys. When a user unlocks their keys, the browser asks
the authenticator for a PRF output: 32 deterministic bytes that only this passkey can produce. HKDF-SHA-256 turns
them into a non-extractable AES-256-GCM key-encryption key (KEK), which decrypts the user's two RSA private keys:
one to decrypt file keys, one to sign the manifest. The server keeps these private keys, but only in encrypted
form, and has no way to open them.

![Key derivation chain: the authenticator produces a PRF output, HKDF-SHA-256 derives the KEK in browser memory, and the KEK wraps the RSA-OAEP and RSA-PSS private keys stored on the server](docs/images/key-derivation.svg)

### Envelope encryption

Each file gets its own random data-encryption key (DEK). The file name, exam date and content are serialised
together and encrypted once with AES-256-GCM, so the server does not even know the names of the documents it
hosts. The DEK is then wrapped with RSA-OAEP for each person allowed to read the file: granting access to a doctor
adds an envelope, and revoking it deletes the envelope.

![Envelope encryption: the file is encrypted once with its DEK, and the DEK is wrapped separately with the patient's and the doctor's public keys](docs/images/envelope-encryption.svg)


### Signed manifest

Encryption protects each file, but not the list of files. A compromised server could silently delete an
inconvenient exam or add a forged document, and every remaining file would still decrypt correctly. Each record
therefore has a manifest (the list of file identifiers and a version counter) signed with the patient's RSA-PSS
private key. The client verifies the signature, then compares the signed list with the list actually delivered,
in both directions, so that both removals and additions are detected. The server rejects any manifest whose
version does not increase, which blocks the replay of an older, validly signed manifest.

### Access control

- **Deny by default** — every endpoint requires a valid token unless explicitly stated otherwise.
- **Role from the token** — the role is derived from the group carried by the signed token, never from a field
  sent by the client.
- **Object-level checks** — a doctor approved for patient A cannot read the files of patient B.
- **404, not 403** — unauthorised access to a file returns `404 Not Found`: a `403` would confirm to an attacker
  that the file exists.

### Server authentication

The server's public key is carried by its X.509 certificate, signed by a local certificate authority created at
installation. The CA certificate is **transferred out of band**: it is generated on the machine that runs the
project and installed manually in the system trust store, never downloaded from the server itself. On every
connection, the browser checks the signature chain and that the requested hostname appears in the certificate's
`subjectAltName`, and refuses the connection if either check fails. In production, a public CA would replace the
local one; the mechanism stays the same.

### Hardening

`DEBUG=False`, Gunicorn instead of a development server (no interactive debugger), Django admin disabled outside
development, HSTS, strict Content Security Policy, secure cookies, rate limiting with a counter shared between
workers, brute-force detection in Keycloak and full OpenID Connect logout.


## Project structure

```text
hospital-security/
├── README.md
├── docs/images/                                # Diagrams used in this README
└── 5SEC1AL_2025-2026_Projet_Groupe31_ThemeHospital/
    ├── install.sh                              # One-command installation: secrets, certificates, containers
    ├── docker-compose.yml                      # The four services
    ├── .env.example                            # Configuration template (secrets are generated by install.sh)
    ├── Vagrantfile                             # Clean Ubuntu 22.04 VM to test the installation from scratch
    ├── certs/
    │   ├── generate-certs.sh                   # Local certificate authority and server certificate
    │   └── server.ext                          # subjectAltName of the server certificate
    ├── keycloak/import/
    │   └── hospital-realm.json                 # Realm imported at first startup
    ├── backend/                                # Django REST API
    │   ├── config/                             # Settings (security hardening), URLs, WSGI
    │   ├── accounts/                           # Keycloak token authentication, profiles, public keys,
    │   │                                       # doctor-patient links, permissions, rate limiting
    │   ├── records/                            # Encrypted files, wrapped keys, signed manifests
    │   └── docs/                               # Sphinx configuration
    ├── frontend/                               # Vue.js 3 application
    │   ├── nginx.conf                          # HTTPS, CSP and security headers
    │   └── src/
    │       ├── crypto/
    │       │   ├── keys.js                     # PRF, HKDF, KEK, RSA key pairs, signatures
    │       │   └── files.js                    # Envelope encryption of the documents
    │       ├── services/                       # API client, authentication, enrollment, records,
    │       │                                   # doctors, approvals
    │       └── __tests__/                      # Vitest unit tests of the crypto modules
    ├── docs/                                   # Security checklist answers, Vagrant demo notes (French)
    └── *_medical_records_*.txt                 # Fictitious sample documents for testing
```


## Getting started

### Prerequisites

- **Docker Engine** with the **Docker Compose v2** plugin (Docker Desktop on Windows)
- **OpenSSL** (provided by Git for Windows on Windows)
- A recent **Chromium-based browser**: Microsoft Edge or Google Chrome
- A **WebAuthn authenticator supporting the PRF extension** — see [Authenticator requirements](#authenticator-requirements)

On Ubuntu, `install.sh` installs Docker and OpenSSL if they are missing.

### Installation

**Ubuntu 22.04**

```bash
git clone https://github.com/MGpro-grammer/hospital-security.git
cd hospital-security/5SEC1AL_2025-2026_Projet_Groupe31_ThemeHospital
chmod +x install.sh
./install.sh
```

**Windows 10/11 (PowerShell)** — requires Docker Desktop (started) and Git for Windows.

```powershell
git clone https://github.com/MGpro-grammer/hospital-security.git
cd hospital-security\5SEC1AL_2025-2026_Projet_Groupe31_ThemeHospital
& "C:\Program Files\Git\bin\bash.exe" install.sh
```

> [!NOTE]
> On Windows, call Git Bash explicitly as shown above: a plain `bash` command may start the WSL shell instead,
> which runs in a different environment.

The script is idempotent and can safely be run again. It:

1. installs the missing dependencies (Ubuntu only);
2. creates `.env` from `.env.example`, with a randomly generated `SECRET_KEY`, `POSTGRES_PASSWORD` and
   `KEYCLOAK_ADMIN_PASSWORD`;
3. generates the local certificate authority and the server certificate;
4. builds the images and starts the four services;
5. applies the database migrations and creates the cache table.

### Trust the local certificate authority

This step is **required**. Without it, the browser shows a security warning and, above all, **WebAuthn refuses
to work**: it only runs in a secure context.

**Windows (PowerShell, from the project folder)** — the `CurrentUser` store requires no administrator rights:

```powershell
Import-Certificate -FilePath .\certs\ca.crt -CertStoreLocation Cert:\CurrentUser\Root
```

**Ubuntu — system store**

```bash
sudo cp certs/ca.crt /usr/local/share/ca-certificates/hospital-security-ca.crt
sudo update-ca-certificates
```

**Ubuntu — Chrome / Chromium**, which uses its own NSS database on Linux:

```bash
sudo apt-get install -y libnss3-tools
certutil -d sql:$HOME/.pki/nssdb -A -t "C,," -n "Hospital Security CA" -i certs/ca.crt
```

Restart the browser completely, then open **https://localhost**: the padlock must be closed, with no warning.


### Authenticator requirements

The application derives the key that protects the user's private keys from their authenticator, through the
WebAuthn **PRF** extension (`hmac-secret`). Without it, the application cannot work.

| Component     | Tested configuration                            |
|---------------|-------------------------------------------------|
| System        | Windows 11 (build 26200)                        |
| Browser       | Microsoft Edge 151                              |
| Authenticator | Windows Hello, with the passkey stored on the device |

Recent FIDO2 security keys supporting `hmac-secret` (YubiKey 5 series, SoloKeys) and Chrome on Windows and Linux
work also. Password managers that intercept passkey creation without implementing PRF do not: when
creating the passkey, explicitly choose **This device**.

> [!TIP]
> If the application displays `PRF indisponible sur cet authentificateur`, the passkey was created by a component
> that does not support PRF. Delete it (Windows Settings → Accounts → Passkeys, filter `localhost`), then register
> again and choose **This device**. On computers managed by a school or a company, Windows Hello may be disabled
> by the organisation.

### Usage

The application is available at **https://localhost**. Its user interface is in French.

**Create a patient**

1. **1. Se connecter** → *Register* on the Keycloak page.
2. Enter a username and an email, then create the passkey, choosing **This device**.
3. Back in the application: **2. Créer mon profil**, then **3. Enregistrer mes clés**.

The `patients` group is assigned automatically at registration.

**Create a doctor** — the `doctors` role is never self-assigned: it is the privileged role, granted by the organisation.

1. Register a second account as above.
2. In the Keycloak admin console (`https://localhost:8443`, user `admin`, password in `.env`): realm **hospital** →
   **Users** → the account → **Groups** tab → **Join Group** → `doctors`.
3. Sign in again with this account, then **2. Créer mon profil** (the *Organisation* field appears) and
   **3. Enregistrer mes clés**.

**Walkthrough** — fictitious sample documents are available in the project folder (`*_medical_records_*.txt`).

*As a patient*, after **4. Déverrouiller mes clés**:

- upload an encrypted file to the record;
- **6. Lire mon dossier**: `MANIFESTE VALIDE` confirms that the list delivered by the server matches the list
  signed by the patient;
- **7. Chercher un médecin** → **Autoriser**: the browser re-wraps the key of each file for this doctor;
- **Retirer**: the link and all of the doctor's keys are deleted.

*As a doctor*:

- **7. Chercher un patient** → **Demander l'accès**: the request stays pending until the patient approves it;
- **Ouvrir le dossier**, then **Ouvrir** a file;
- **9. Déposer** a file: it arrives as `pending_approval` and does not enter the record until the patient approves
  and countersigns it;
- **Remplacer** / **Demander la suppression**: proposals submitted to the patient's approval.

### See for yourself: the server sees nothing

```bash
docker compose exec db psql -U hospital -d hospital -P pager=off -c "SELECT id, LEFT(ciphertext, 40) FROM records_medicalfile;"
```

No file name, no exam date, no content: all three are serialised and encrypted together in a single blob.

```bash
docker compose exec db psql -U hospital -d hospital -P pager=off -c "SELECT file_id, recipient_sub, LEFT(wrapped_dek, 24) FROM records_wrappedkey ORDER BY file_id;"
```

For the same file, two envelopes (the patient's and the doctor's) **without a single byte in common**, even
though they protect the same key. The encrypted file itself is stored only once.


## Testing

The automated tests target the security-critical code: the cryptography running in the browser and the
cross-record access control on the server.

| Scope                         | Tests | What is verified                                                                                   |
|-------------------------------|------:|----------------------------------------------------------------------------------------------------|
| Frontend — `crypto/keys.js`   | 6     | Same PRF output gives the same KEK, another output a different one; private key wrap/unwrap cycle; wrong KEK rejected; no plaintext trace of the private key; base64 round trip |
| Frontend — `crypto/files.js`  | 7     | Name, date and content restored; neither file name nor date leak; tampered blob detected; DEK shared through RSA without duplicating the file; DEK unreadable by a third party; authentic manifest accepted; file removed from the manifest detected |
| Backend — `records`           | 2     | Replacing a file in another patient's record is refused; replacing a file in the same record is accepted |

All commands below are run from the `5SEC1AL_2025-2026_Projet_Groupe31_ThemeHospital/` folder.

**Backend tests**

```bash
docker compose exec django python manage.py test
```

**Frontend tests**

```bash
docker run --rm -v "${PWD}/frontend:/app" -w /app node:22-alpine sh -c "npm ci && npx vitest run"
```

### Security audits

**Django deployment checklist**

```bash
docker compose exec django python manage.py check --deploy
```

Expected: `System check identified no issues (1 silenced)`. The silenced check is `security.W021` (HSTS preload),
which does not apply to `localhost`; the justification is documented in `backend/config/settings.py`.

**Dependency audits**

```bash
docker run --rm -v "${PWD}/frontend:/app" -w /app node:22-alpine npm audit
docker run --rm -v "${PWD}/backend:/app" -w /app python:3.12-slim sh -c "pip install -q pip-audit && pip-audit -r requirements.txt"
```


## Developer documentation

Both documentations are generated from the comments in the source code, so they cannot drift away from the
implementation. The code comments, and therefore the generated documentation, are written in French.

**Backend (Sphinx)**

```bash
docker run --rm -v "${PWD}/backend:/app" -w /app python:3.12-slim sh -c "pip install -q -r requirements.txt -r requirements-docs.txt && sphinx-build -b html docs docs/_build"
```

Output: `backend/docs/_build/index.html`

**Frontend (JSDoc)**

```bash
docker run --rm -v "${PWD}/frontend:/app" -w /app node:22-alpine npx --yes jsdoc -c jsdoc.json
```

Output: `frontend/docs/index.html`

## Operations

| Action                         | Command                                        |
|--------------------------------|------------------------------------------------|
| Show the status of the services | `docker compose ps`                           |
| Follow the backend logs        | `docker compose logs -f django`                |
| Stop (data is kept)            | `docker compose down`                          |
| Restart                        | `docker compose up -d`                         |
| **Reset everything**           | `docker compose down -v`, then run `install.sh` again |

`docker compose down -v` deletes the database **and** the Keycloak accounts. The realm is re-imported
automatically at the next startup, but user accounts must be created again.

> [!WARNING]
> After a reset, the old passkeys remain registered in the operating system although the matching accounts no
> longer exist. Delete them before registering again (Windows Settings → Accounts → Passkeys, filter `localhost`).


## Known limitations

These limitations are identified and assumed. Most of them are inherent to end-to-end encryption rather than
to this implementation.

| Limitation                               | Explanation                                                                                     |
|------------------------------------------|-------------------------------------------------------------------------------------------------|
| **Losing the passkey means losing the record** | The key that protects the private keys is derived from the authenticator and stored nowhere. Deleting the passkey makes the record permanently unreadable. Neither the server nor an administrator can help: if they could, they could also read it. |
| **A downloaded file cannot be revoked**  | Removing a doctor stops future access, not the copy they have already decrypted. No system can take back data that has already been delivered. |
| **Public key substitution by the server** | Users' public keys are distributed by the API. A malicious server could replace a doctor's public key with its own and read the files a patient believes they are sharing with that doctor. Closing this gap requires out-of-band verification between users (comparing key fingerprints, scanning a QR code in person), as in end-to-end encrypted messaging apps. This is beyond the scope of the project. |
| **Physical remanence in the database**   | PostgreSQL does not immediately overwrite deleted disk blocks. But deleting a file also deletes its keys, so the encrypted blob, even if recovered, can never be read again. This is crypto-shredding: instead of relying on erasure, the key is destroyed. |
| **Browser memory**                       | No web application can guarantee that RAM is wiped. Keys are non-extractable `CryptoKey` objects, never stored in `localStorage`, and the **Verrouiller** button removes the only usable reference to them. |


## Team

| Member                                                                      | Role         |
|-----------------------------------------------------------------------------|--------------|
| **Georges Mouratidis** ([@MGpro-grammer](https://github.com/MGpro-grammer)) | Co-developer |
| **Ian Grande** ([@ian-grande-dev](https://github.com/ian-grande-dev))       | Co-developer |

The project was designed and built jointly, with both members working side by side on every part of the
system: cryptography, backend, frontend and infrastructure. This was a deliberate choice for a project where
the security of medical data leaves no room for approximation.

## Roadmap

- [ ] Verify users' public keys out of band (key fingerprints or QR codes) to close the public key substitution gap.
- [ ] Allow a backup authenticator, by wrapping the private keys under a second KEK, so that losing one passkey
  no longer means losing the record.
- [ ] Extend the backend test suite: authentication, permissions, rate limiting, manifest versioning and the
  approval workflow.
- [ ] Add end-to-end tests of the full patient and doctor journey, using a virtual WebAuthn authenticator.
- [ ] Run the tests and dependency audits on every push with a continuous integration pipeline.
- [ ] Remove the unused Vue Router and Pinia scaffolding.
- [ ] Make the user interface available in English.

## Acknowledgements

- Our teachers at HE2B ESI for their guidance throughout the Security course.
- A special thanks to Ian Grande for a rigorous and demanding collaboration from start to finish.
- [Keycloak](https://www.keycloak.org/), [Django](https://www.djangoproject.com/) and [Vue.js](https://vuejs.org/)
  for the open-source foundations of the project.
- The [W3C Web Authentication](https://www.w3.org/TR/webauthn-3/) specification and its PRF extension, which make
  passwordless, hardware-bound encryption keys possible in the browser.
