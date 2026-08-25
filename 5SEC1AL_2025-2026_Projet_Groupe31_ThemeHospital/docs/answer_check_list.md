# Réponses à la check-list de sécurité

**Projet 5SEC1A — Groupe 31**
Mouratidis Georges (62218) · Grande Ian (62265)

Ce document répond aux quinze questions de `checklist.pdf`. Chaque réponse indique **ce qui a été implémenté**, **comment le démontrer**, et **les limites assumées**.

Conformément à la consigne — *« It is important to be able to answer all these questions, even if the answer means there is a vulnerability »* — les deux points sur lesquels le projet est faible sont traités aussi longuement que les autres, avec les mesures qui les atténuent et ce que nous ferions pour les corriger.

---

## 1. Confidentialité

### Les données sensibles sont-elles transmises et stockées correctement ?

**Oui.** Le contenu, le nom et la date d'examen de chaque fichier sont sérialisés puis chiffrés **ensemble** dans un unique bloc AES-256-GCM, dans le navigateur, avant tout appel réseau.

```
   fichier ---[DEK AES-256-GCM]---> bloc chiffre (stocke UNE fois)
      DEK ---[RSA-OAEP, cle publique du patient]---> enveloppe 1
      DEK ---[RSA-OAEP, cle publique du medecin]---> enveloppe 2
```

Le serveur ne connaît **même pas le nom** des documents qu'il héberge.

Les clés privées RSA des utilisateurs sont stockées sur le serveur, mais **chiffrées** par une clé (KEK) dérivée de l'authentificateur matériel via WebAuthn PRF puis HKDF-SHA256. Cette KEK n'est stockée nulle part : elle est recalculée à chaque session et n'existe qu'en mémoire du navigateur, sous forme d'objet `CryptoKey` non extractible.

### Les requêtes sensibles sont-elles transmises de façon sécurisée ?

**Oui.** TLS 1.2/1.3 sur l'intégralité des canaux — navigateur ↔ nginx, navigateur ↔ Django, navigateur ↔ Keycloak, Django ↔ Keycloak. Le port 80 n'existe que pour rediriger en 301 vers HTTPS, et HSTS empêche même la première requête en clair.

Aucun canal en clair n'existe : le port 8080 de Keycloak a été retiré dès la Phase 1.

### Un administrateur système peut-il accéder aux données sensibles ?

**Non — et c'est démontrable.**

Un administrateur de la base voit : des blocs base64, des clés de fichier chiffrées, et des clés privées chiffrées. Aucune colonne de la base ne contient la clé permettant de déchiffrer quoi que ce soit.

```
docker compose exec db psql -U hospital -d hospital -P pager=off \
  -c "SELECT keycloak_sub, LEFT(encrypted_private_key,20), private_key_iv FROM accounts_userkeys;"
```

**Preuve par l'audit** : un `pg_dump` complet de la base ne contient ni les noms de fichiers, ni les dates d'examen, ni le contenu des documents. Vérifié (tests 11.1 à 11.3).

### Ce qui est délibérément en clair

L'identité des patients et des médecins — nom, prénom, date de naissance, organisation — est stockée en clair. **C'est une décision, pas un oubli** :

- `health.pdf` ne classe pas l'identité parmi les données sensibles ; il désigne le contenu, les noms et les dates des fichiers ;
- un médecin doit pouvoir **rechercher un patient** pour lui demander l'accès à son dossier. Chiffrer l'identité rendrait cette recherche impossible sans révéler autre chose.

Ce que le serveur peut donc déduire : qu'une personne nommée X possède un dossier de N fichiers, et quels médecins y ont accès. C'est le **métadonnées** que l'architecture ne protège pas.

---

## 2. Durcissement du schéma d'authentification

**Authentification sans mot de passe**, par WebAuthn (Keycloak, flux `browser-webauthn-passwordless`), avec :

| Paramètre | Valeur | Effet |
|---|---|---|
| `residentKey` | `required` | clé découvrable, aucun identifiant à saisir |
| `userVerification` | `required` | PIN ou biométrie **obligatoire** à chaque usage |
| `attestation` | `none` | aucune donnée identifiant le modèle d'authentificateur n'est collectée |

**Il n'y a pas de mot de passe à voler, à deviner, à rejouer ou à réutiliser ailleurs.** L'authentification repose sur possession (l'authentificateur) **et** inhérence ou connaissance (biométrie ou PIN) : c'est structurellement une authentification multifacteur.

`Direct access grants` est désactivé sur le client Keycloak — sans quoi un attaquant aurait pu obtenir un jeton par simple appel API, contournant entièrement WebAuthn.

**Détection de force brute** activée sur le realm (verrouillage temporaire, 5 échecs, attente 1 → 15 min, réinitialisation 12 h).

### Captcha : choix documenté de ne pas l'implémenter

Un captcha empêche la création automatisée de comptes. Or l'inscription exige la **création d'une passkey WebAuthn** avec `userVerification: required` : authentificateur matériel présent physiquement, vérification par PIN ou biométrie, interaction humaine avec le système d'exploitation. **Un script ne peut pas faire cela** — c'est un contrôle anti-automatisation plus fort qu'un captcha, et qui ne se contourne pas avec une ferme de résolution.

L'argument décisif est ailleurs : reCAPTCHA transmettrait à Google, à chaque affichage du formulaire, l'adresse IP du visiteur, son empreinte de navigateur et l'URL consultée. Sur l'inscription d'une **application de dossiers médicaux**, cela revient à signaler à un tiers qu'une personne donnée s'inscrit à un service de santé. C'est une régression de confidentialité sur un projet dont toute la démarche consiste à ne rien confier à personne.

**Preuve à zéro divulgation** : non implémentée. Elle n'apporterait rien ici, WebAuthn étant déjà un protocole de défi-réponse où aucun secret ne transite.

---

## 3. Intégrité des données stockées

**Oui.** AES-256-**GCM** est un mode chiffré **authentifié** : il produit une étiquette d'authentification vérifiée au déchiffrement. Toute altération d'un octet du bloc chiffré, du vecteur d'initialisation ou de l'étiquette fait échouer l'opération — le navigateur lève une exception au lieu de restituer des données corrompues.

Un serveur qui modifierait un bloc chiffré ne produirait pas un faux document : il produirait une erreur.

La même protection s'applique aux clés privées des utilisateurs, chiffrées en AES-GCM avec la KEK.

---

## 4. Intégrité des séquences

**Oui — et c'est le point sur lequel nous avons le plus travaillé.**

Le chiffrement protège **chaque fichier**, il ne protège pas **la liste**. Sans mesure spécifique, un serveur compromis pourrait supprimer un examen gênant ou ajouter un faux document : chaque fichier restant serait parfaitement valide, seul l'ensemble aurait été falsifié.

**Solution : un manifeste signé.** Le dossier possède une liste des identifiants et un compteur de version, sérialisés en JSON et **signés par la clé privée RSA-PSS du patient**. Le client :

1. vérifie la signature du manifeste avec la clé publique du patient ;
2. compare la liste signée à la liste effectivement livrée par le serveur, **dans les deux sens**.

La bidirectionnalité est essentielle : une comparaison dans un seul sens détecterait une suppression **ou** un ajout, jamais les deux.

```js
for (const id of signes) if (!livres.has(id)) return "Fichier SUPPRIME par le serveur"
for (const id of livres) if (!signes.has(id)) return "Fichier AJOUTE hors manifeste"
```

**Contre le rejeu** : le compteur de version est monotone. Le serveur refuse (409) tout manifeste dont la version n'augmente pas. Un attaquant muni d'un jeton volé ne peut donc pas restaurer un ancien manifeste valablement signé pour faire « disparaître » un fichier récent.

**Le serveur ne peut pas fabriquer de manifeste** : il ne possède aucune clé de signature. C'est pourquoi un fichier déposé par un médecin arrive hors manifeste et n'entre dans le dossier qu'après approbation et contresignature du patient.

---

## 5. Non-répudiation — ⚠️ PARTIELLE

**Réponse honnête : partiellement assurée.**

### Ce qui est couvert

Le patient **ne peut pas nier** avoir validé la composition de son dossier : le manifeste est signé par sa clé privée RSA-PSS, dont le serveur n'a jamais eu connaissance. Cela couvre :

- l'ajout d'un fichier au dossier ;
- la suppression d'un fichier ;
- l'approbation d'un dépôt fait par un médecin.

### Ce qui ne l'est pas

Quand un **médecin** dépose un fichier, **rien n'est signé de sa main**. Le champ `uploaded_by` est renseigné par le serveur d'après le claim `sub` du jeton vérifié.

```
   ce que nous avons :  le SERVEUR atteste que le Dr X a depose
                        -> imputabilite (accountability)

   ce qu'il faudrait :  le Dr X SIGNE son depot avec sa cle privee
                        -> non-repudiation
```

La différence est réelle : un serveur compromis pourrait attribuer un dépôt à n'importe quel médecin. Celui-ci pourrait affirmer « ce n'est pas moi, le serveur ment » — et il aurait techniquement raison. L'attribution repose sur la parole du serveur, pas sur une preuve cryptographique.

De même, l'approbation d'un lien patient–médecin n'est pas signée : elle est enregistrée par le serveur.

### Ce qui atténue le risque

- L'identité provient d'un **jeton signé par Keycloak** (RS256), jamais d'un champ envoyé par le client. Un utilisateur ne peut donc pas se faire passer pour un autre auprès d'un serveur honnête.
- Le fichier déposé est chiffré avec une DEK scellée pour le médecin **et** pour le patient : le déposant a nécessairement eu accès à la clé publique du patient, donc à un lien approuvé.
- Le patient voit le dépôt, peut l'ouvrir, et doit l'approuver explicitement. Un dépôt frauduleux ne peut pas entrer dans le dossier à son insu.

### Ce que nous ferions pour le corriger

Le médecin possède déjà une paire RSA-PSS depuis la Phase 6 — celle qui sert à signer les manifestes pour un patient. Il suffirait de :

1. faire signer par le médecin, à l'upload, un condensé de `{file_id, patient_sub, iv, empreinte du ciphertext, horodatage}` ;
2. stocker cette signature à côté du fichier ;
3. la faire vérifier par le patient à l'approbation, avec la clé publique du médecin obtenue via `LinkSerializer`.

Ce n'est pas un chantier : environ vingt lignes réparties sur trois fichiers. **Le choix de ne pas le faire est un arbitrage de calendrier**, pris à quelques jours de la remise sur un protocole d'upload validé par vingt tests — pas une incompréhension du problème.

---

## 6. Sécurité par le secret

**Non — le principe de Kerckhoffs est respecté.**

Tout le code est destiné à être lu : il est livré dans un dépôt git accessible aux enseignants. La sécurité repose **exclusivement** sur :

- les clés privées RSA des utilisateurs, jamais transmises en clair ;
- la sortie du PRF de l'authentificateur, jamais stockée ;
- la clé de signature du realm Keycloak, régénérée à chaque installation ;
- les secrets d'installation (`SECRET_KEY`, mots de passe), **tirés au sort par `install.sh`**.

Les éléments publics le sont assumément : le sel du PRF, les paramètres HKDF, le RP ID, les identifiants de client OIDC. Les connaître n'aide en rien.

**Ce point a été appliqué concrètement** : l'export du realm Keycloak contenait les clés privées du realm (`components/KeyProvider`). Elles ont été **retirées avant versionnement** — sans quoi n'importe qui aurait pu forger un jeton valide et le contrôle d'accès entier serait tombé. Keycloak régénère ses clés à l'import : chaque installation a les siennes.

Même raisonnement pour `install.sh`, qui tire au sort trois secrets à chaque installation : **une clé partagée entre deux installations n'est plus une clé**.

---

## 7. Vulnérabilité aux injections

**Non**, et l'audit statique est vérifiable.

### SQL

Toutes les requêtes passent par l'ORM Django, y compris les deux recherches par nom, qui utilisent des objets `Q` :

```python
Doctor.objects.filter(Q(last_name__icontains=q) | Q(first_name__icontains=q))
```

Aucune concaténation de chaîne, aucune interpolation. Recherche exhaustive dans `accounts/`, `records/` et `config/` : **aucun `.raw()`, `.extra()`, `RawSQL` ni `cursor.execute`**.

### JavaScript / XSS

**Aucun `v-html` dans le projet.** Vue échappe automatiquement tout ce qui passe par `{{ }}` : un médecin qui se nommerait `<script>alert(1)</script>` verrait son nom affiché comme du texte.

Aucun `innerHTML`, `document.write`, `eval(` ni `new Function`.

En défense de fond, une **CSP stricte** servie par nginx :

```
default-src 'self'; script-src 'self'; style-src 'self';
connect-src 'self' https://localhost:8000 https://localhost:8443;
frame-ancestors 'none'; base-uri 'self'; object-src 'none'
```

Même si un script étranger parvenait à être injecté, le navigateur refuserait de l'exécuter. Aucun `unsafe-inline`, aucun CDN.

### URL

Les identifiants de fichier sont des **UUID typés dans le routage** (`<uuid:file_id>`) : une valeur malformée est rejetée par Django avant d'atteindre la vue. Les UUID sont opaques — ils ne révèlent ni ordre, ni date, ni nombre de fichiers.

### Parseurs dédiés

Le manifeste est du JSON parsé par `JSON.parse`, **après** vérification de sa signature RSA-PSS. On ne parse jamais une donnée dont l'authenticité n'a pas d'abord été établie.

---

## 8. Rémanence des données

**Analysée, avec des limites honnêtes.**

### Côté navigateur

| Élément | Sort |
|---|---|
| Jeton d'accès | variable de module, **jamais** `localStorage`. Meurt à la fermeture de l'onglet |
| `code_verifier` PKCE | `sessionStorage`, **supprimé** dès l'échange du code |
| Clés privées, KEK, DEK | objets `CryptoKey` **non extractibles** — le JavaScript ne peut pas lire leurs octets, même compromis |
| Bouton **Verrouiller** | retire la seule référence utilisable, sans quitter la session |
| Déconnexion OIDC | quitte la page : tout le contexte est détruit |

**Limite** : le navigateur peut avoir laissé des fragments en mémoire processus ou dans un fichier d'échange du système. **Aucune application web ne peut garantir l'effacement de la RAM** — c'est hors de portée de JavaScript.

### Côté serveur

La suppression est **réelle** : `delete()` retire les lignes, les `WrappedKey` tombent en cascade.

**Limite** : PostgreSQL ne réécrit pas immédiatement les blocs disque. Une ligne supprimée reste physiquement présente jusqu'au passage de `VACUUM`, et une sauvegarde antérieure la contient encore.

### Pourquoi l'architecture répond mieux qu'un effacement

Le serveur n'a jamais détenu que :

```
   bloc chiffre AES-256-GCM   +   DEK chiffree en RSA-OAEP
   (illisible sans la DEK)        (illisible sans la cle privee)
```

Détruire les `WrappedKey`, c'est détruire l'unique chemin vers la DEK. Le bloc chiffré, même exhumé d'un secteur disque ou d'une vieille sauvegarde, **ne redeviendra jamais lisible**.

C'est le principe du ***crypto-shredding*** : on n'efface pas la donnée, on détruit la clé — et le résultat est **plus fort**, parce qu'il ne dépend ni du système de fichiers, ni des sauvegardes, ni de la bonne volonté de l'hébergeur.

---

## 9. Forgery de requêtes (CSRF)

**Structurellement sans objet — ce n'est pas une lacune.**

L'authentification passe **exclusivement** par un en-tête `Authorization: Bearer <jeton>`, jamais par un cookie. `CORS_ALLOW_CREDENTIALS = False`.

Le CSRF exploite le fait que le navigateur **joint automatiquement** les cookies d'un site à toute requête vers ce site, y compris déclenchée depuis un autre site. Un en-tête `Authorization` n'est jamais ajouté automatiquement : seul le code de notre application, chargé depuis notre origine, peut le poser.

Un site tiers ne peut donc pas faire porter le jeton de l'utilisateur.

Défenses complémentaires : liste blanche stricte des origines CORS, `frame-ancestors 'none'` et `X-Frame-Options: DENY` contre le clickjacking, `SameSite` et `Secure` sur les cookies de session Django (qui ne servent qu'à l'admin, désactivé en production).

---

## 10. Surveillance de l'activité — 🔴 FAIBLE

**Réponse honnête : c'est le point faible du projet.**

### Ce qui existe

| Source | Contenu |
|---|---|
| Journal d'accès gunicorn | méthode, URL, code de statut, horodatage, IP |
| Journal `django.request` | erreurs applicatives, niveau `ERROR`, sur la sortie standard du conteneur |
| Journal Keycloak | connexions, échecs, actions requises |
| Détection de force brute Keycloak | verrouillage après 5 échecs |
| Limitation de débit DRF | `429` au-delà des seuils, compteur partagé en base |

Ces journaux permettent de constater qu'un `sub` donné a appelé `GET /api/records/files/<uuid>` à telle heure. C'est déjà une trace exploitable *a posteriori*.

### Ce qui manque, et pourquoi c'est sérieux

**Il n'existe aucun journal applicatif d'accès aux dossiers.** Les journaux HTTP sont des journaux techniques : non structurés, non requêtables, non conservés durablement (ils disparaissent avec le conteneur), et **jamais consultables par le patient**.

Conséquence concrète : si un médecin autorisé consultait chaque semaine le dossier d'une personnalité publique sans aucune raison médicale, **personne ne pourrait le constater** — ni le patient, ni l'établissement, ni un auditeur.

C'est une faiblesse d'une nature différente des autres. Tous nos autres contrôles empêchent les accès **illégitimes**. Le journal d'accès est le seul contrôle qui existe contre l'**abus d'un accès légitime** — et notre modèle de menace repose entièrement sur des accès légitimes accordés par le patient.

Dans un système de dossiers médicaux réel, le journal d'accès est une **obligation légale**, pas une option.

### Détection d'anomalies : non implémentée

Rien ne détecte un comportement inhabituel : consultations en rafale, accès nocturnes, médecin consultant soudainement des dizaines de dossiers. La limitation de débit borne le **volume**, elle ne juge pas la **nature** des accès.

### Client lanceur d'alerte : non implémenté

Aucun canal permettant à un utilisateur de signaler un comportement suspect.

### Ce qui atténue le risque

- Un médecin n'accède qu'aux dossiers pour lesquels le patient l'a **explicitement autorisé**, et le patient peut retirer cette autorisation à tout moment ;
- le retrait détruit les clés : l'accès futur devient cryptographiquement impossible, pas seulement interdit ;
- la liste des médecins autorisés est visible du patient à tout moment (`GET /api/links`) — c'est une forme de transparence, à défaut d'un journal.

### Ce que nous ferions

1. **Un modèle `AccessLog`** en écriture seule — `(qui, quel dossier, quel fichier, quand, depuis quelle IP)` — alimenté par `list_record` et `get_file`. Environ trente lignes.
2. **Un écran « qui a consulté mon dossier »** côté patient, alimenté par ce journal. C'est ce qui transforme une trace technique en contrôle réel : le patient devient l'auditeur de son propre dossier.
3. **Une détection d'anomalies simple** : alerter le patient au-delà de N consultations par jour par un même médecin, ou lors d'un accès hors plage horaire habituelle.
4. **Un journal inviolable** : chaîner les entrées par condensé (chaque entrée contient le condensé de la précédente), afin qu'un administrateur ne puisse pas effacer une consultation gênante sans rompre la chaîne.

Le point 4 mérite d'être souligné : un journal d'accès que l'administrateur peut modifier ne protège pas contre l'administrateur. C'est le même raisonnement que le manifeste signé, appliqué aux traces.

---

## 11. Composants avec vulnérabilités connues

**Non, à la date de la remise.**

```
docker run --rm -v ${PWD}/frontend:/app -w /app node:22-alpine npm audit
  -> found 0 vulnerabilities

docker run --rm -v ${PWD}/backend:/app -w /app python:3.12-slim \
  sh -c "pip install pip-audit -q && pip-audit -r requirements.txt"
  -> No known vulnerabilities found
```

Les deux audits tournent sur les **mêmes images que le build** (`node:22-alpine`, `python:3.12-slim`) : auditer avec une autre version n'auditerait pas le bon arbre de dépendances.

**Limite honnête** : ces outils ne connaissent que les vulnérabilités **publiées**. « 0 vulnerabilities » signifie « rien de connu à ce jour », pas « sûr ».

**Réduction de surface** : `prf-spike.html` (prototype de la Phase 2, servi publiquement et générant ses challenges côté client) a été supprimé du livrable. La dépendance la plus sûre est celle qu'on n'a pas.

---

## 12. Système à jour

**Oui, et de façon reproductible.**

Toutes les versions sont **épinglées** : images Docker (`postgres:16`, `quay.io/keycloak/keycloak:26.7.2`, `node:22-alpine`, `python:3.12-slim`, `nginx:1.31-alpine`), dépendances Python (`requirements.txt`) et JavaScript (`package-lock.json`).

L'épinglage est une décision de sécurité, pas de confort :

- **reproductibilité** : le correcteur obtient exactement ce que nous avons testé ;
- **auditabilité** : `pip-audit` ne peut se prononcer que s'il sait quelle version sera installée. Un `requirements.txt` sans numéros rendrait l'audit ininterprétable.

**Reproductibilité et auditabilité sont la même exigence vue sous deux angles.**

**Contrepartie assumée** : une version épinglée ne se met pas à jour toute seule. La mise à jour devient un acte délibéré, précédé d'un audit et suivi des tests — ce qui est le comportement souhaitable pour un système de santé, où une mise à jour non testée est un risque en soi.

---

## 13. Contrôle d'accès (OWASP A01)

**Non cassé.**

**Refus par défaut** : `DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]`. Tout endpoint exige un jeton valide, sauf mention explicite du contraire — `/api/health` est le seul endpoint public.

**Le rôle vient du jeton signé**, jamais d'un champ envoyé par le client. Un utilisateur ne peut pas se déclarer médecin : `create_profile` choisit le sérialiseur d'après le groupe Keycloak, et `upload_file` déduit le statut du fichier du même groupe.

**Contrôle objet par objet** — `can_access_record` :

```python
patient  -> user.sub == patient_sub
medecin  -> il existe un lien APPROVED entre lui et ce patient
sinon    -> refus
```

Un médecin approuvé pour le patient A ne peut pas lire les fichiers du patient B.

**Double barrière sur les fichiers** : `get_file` exige à la fois un accès légitime au dossier **et** une `WrappedKey` au nom de l'appelant. Sans clé, le bloc reste inexploitable même si le contrôle était contourné.

**404 plutôt que 403** en cas d'accès illégitime à un fichier : un 403 confirmerait à un attaquant que ce fichier **existe**, permettant d'énumérer les identifiants.

### Une faille trouvée et corrigée — à mentionner spontanément

Le champ `replaces` (édition d'un fichier) était accepté sans vérification. Un médecin autorisé par Alice **et** par Bob pouvait déposer chez Alice un fichier déclarant remplacer un fichier de **Bob**. À l'approbation par Alice, le serveur aurait supprimé un document du dossier de Bob, qui n'avait rien demandé.

**La cause, à formuler telle quelle** : *le contrôle d'accès sur l'objet principal ne protège pas les objets qu'il référence*. Django vérifiait bien qu'Alice pouvait approuver *son* fichier ; personne ne vérifiait le droit sur l'objet **pointé**. Une clé étrangère garantit que la cible **existe**, jamais qu'elle appartient au bon dossier.

**Corrigé en défense en profondeur** : contrôle à l'upload (400) **et** contrôle à l'approbation. On ne fait pas reposer une conséquence irréversible sur un seul contrôle. Couvert par deux tests unitaires — l'attaque et la contre-épreuve.

---

## 14. Authentification (OWASP A07)

**Non cassée.**

- **Aucun mot de passe** : rien à deviner, à rejouer, à réutiliser ailleurs, ni à retrouver dans une fuite d'un autre site.
- **OpenID Connect Authorization Code + PKCE S256**, client public. Le code d'autorisation intercepté est inutilisable sans le `code_verifier`, qui ne quitte jamais le navigateur.
- **Validation stricte du jeton** côté Django : algorithme `RS256` **imposé** (pas de confusion d'algorithme, pas d'acceptation de `alg: none`), et `exp`, `iat`, `iss`, `aud`, `sub` exigés. Message d'erreur générique — un message précis renseignerait l'attaquant.
- **Jeton en mémoire uniquement**, jamais en `localStorage` : il disparaît à la fermeture de l'onglet et reste hors de portée d'un script injecté.
- **Déconnexion complète** (*RP-Initiated Logout* OIDC) : la session Keycloak est fermée, pas seulement le jeton local.

### Une faille trouvée et corrigée — à mentionner spontanément

L'ancien `logout()` se contentait de `accessToken = null`. Keycloak conservait sa session sous forme de cookie : un nouveau « Se connecter » **reconnectait silencieusement le même utilisateur**. Sur un poste partagé — un ordinateur de salle de consultation — cela revient à laisser sa session ouverte au suivant.

Corrigé par le *RP-Initiated Logout* prévu par la spécification, avec `id_token_hint`.

**Rôle privilégié jamais auto-attribué** : l'inscription place l'utilisateur dans `patients` (groupe par défaut du realm) ; `doctors` est accordé manuellement par un administrateur. Un attaquant qui s'inscrit obtient le rôle le moins puissant.

**Révocation à deux étages** : Keycloak désactive le compte (plus d'authentification possible) **et** `DELETE /api/users/me` détruit tout le matériel cryptographique (plus rien à déchiffrer). *C'est la destruction des clés qui rend les données inaccessibles, pas le contrôle d'accès.*

---

## 15. Configuration générale

**Non mal configurée — et c'est vérifié par un outil officiel.**

```
docker compose exec django python manage.py check --deploy
  -> System check identified no issues (1 silenced).
```

`check --deploy` est l'audit de déploiement intégré à Django : une quinzaine de points connus.

Le contrôle écarté est `security.W021` (préchargement HSTS), sans objet pour `localhost` — la liste de préchargement est gravée dans le code source des navigateurs et personne ne peut y soumettre `localhost`. La justification est écrite dans `settings.py`, à l'endroit où le contrôle est écarté.

**Le `(1 silenced)` est la bonne réponse, pas un pis-aller** : il indique un contrôle examiné et écarté en connaissance de cause. Un audit qui n'affiche jamais rien parce qu'on a tout fait taire serait suspect.

### Points de configuration à citer

| Élément | Valeur |
|---|---|
| `DEBUG` | `False` |
| Serveur | **gunicorn** — aucun débogueur interactif |
| Admin Django | **désactivé** hors développement |
| En-têtes | HSTS, `nosniff`, `Referrer-Policy`, `X-Frame-Options`, CSP |
| `server_tokens` | `off` — la version de nginx n'est pas divulguée |
| Cookies | `Secure`, `HttpOnly` |
| Secrets | tirés au sort à l'installation, jamais versionnés |

### Une faille trouvée et corrigée — à mentionner spontanément

Le projet tournait sous `runserver_plus`, qui active le **débogueur Werkzeug** : une console Python interactive accessible depuis un navigateur, dont le PIN apparaissait en clair dans les journaux. Avec `DEBUG=True`, la moindre erreur révélait le code source, les requêtes SQL et les variables d'environnement — **mot de passe PostgreSQL compris**.

Analogie : porte blindée, coffre chiffré, clés réparties… et une console d'administration ouverte dans le hall.

**L'admin Django a été désactivé** pour une raison du même ordre : il s'ouvre avec un **mot de passe classique** dans un système sans mot de passe. *Un attaquant n'attaquerait jamais WebAuthn : il attaquerait le mot de passe de l'administrateur.* Principe du maillon faible.

---

# Annexe A — Les six démonstrations à préparer

| # | Ce qu'on montre | Commande / geste |
|---|---|---|
| 1 | **La base ne contient que du chiffré** | `pg_dump` puis recherche du nom de fichier, de la date d'examen et d'un mot du contenu → aucune correspondance |
| 2 | **Deux enveloppes indépendantes pour la même clé** | `SELECT file_id, recipient_sub, LEFT(wrapped_dek,24) FROM records_wrappedkey` → deux lignes par fichier, sans un octet commun |
| 3 | **Le manifeste détecte la falsification** | Un fichier déposé par un médecin est en base mais **hors manifeste** ; `MANIFESTE VALIDE` reste affiché tant que le patient n'a pas contresigné |
| 4 | **Déchiffrement de bout en bout par le médecin** | Fichier chiffré par le navigateur du patient, ouvert par celui du médecin, manifeste vérifié au passage |
| 5 | **La limitation de débit se déclenche** | 35 appels à `/api/health` → une trentaine de `200`, puis des `429` |
| 6 | **Installation sur machine vierge** | VM Vagrant : `which docker` → rien, `./install.sh`, `https://localhost` répond |

---

# Annexe B — Les limites à énoncer spontanément

Les annoncer avant qu'on ne les trouve vaut mieux que de les défendre après.

| Limite | Formulation |
|---|---|
| **Journal d'accès absent** | Le seul contrôle contre l'abus d'un accès **légitime** manque. Voir question 10 pour ce que nous ferions. |
| **Non-répudiation partielle** | Les dépôts de médecins sont imputables, pas non-répudiables. Voir question 5. |
| **Perte de clé = perte du dossier** | La clé est dérivée de l'authentificateur et n'est stockée nulle part. Ni le serveur ni un administrateur ne peuvent aider — **s'ils le pouvaient, c'est qu'ils pourraient lire**. |
| **Fichier déjà téléchargé non révocable** | Aucun système ne reprend une donnée déjà livrée. La révocation empêche l'accès **futur**. |
| **Substitution de clé publique** | Les clés publiques des utilisateurs sont distribuées par l'API. Un serveur malveillant pourrait en substituer une. Fermer cette porte exigerait une vérification hors bande entre utilisateurs — empreinte lue de vive voix, QR code en présentiel, le modèle des messageries chiffrées. |
| **Métadonnées non protégées** | Le serveur sait qu'une personne nommée X possède N fichiers et quels médecins y ont accès. Seul le **contenu** est protégé. |
| **Rémanence physique et mémoire** | PostgreSQL ne réécrit pas les blocs supprimés ; aucune application web ne peut effacer la RAM. Le *crypto-shredding* répond mieux qu'un effacement. |