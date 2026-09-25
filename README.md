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

  