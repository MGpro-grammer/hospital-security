# Démonstration sur machine virtuelle (Vagrant)

Ce document décrit comment reproduire, sur une **Ubuntu 22.04 x64 vierge**, l'installation complète du projet à partir du seul README.

Ce n'est **pas un livrable exigé** par `health.pdf` : le projet doit rester installable sans Vagrant. C'est un outil de vérification et de démonstration.

---

## Pourquoi cette VM existe

`health.pdf` est catégorique :

> *« projects that do not compile according to your exact instructions will not be graded »*
> *« It is expected that your script installs missing dependencies in addition to compiling your code »*

Une machine de développement ment. Elle contient Docker, OpenSSL, des certificats déjà installés, des variables d'environnement déjà en place — accumulés au fil des semaines. Elle ne peut pas dire si le README est complet.

La VM, elle, est nue. Elle ne sait rien du projet.

**Résultat concret** : cette VM a révélé un défaut bloquant d'`install.sh` (voir « Ce que la VM a trouvé » plus bas) que la machine de développement était structurellement incapable de détecter.

---

## Le parti pris : aucun provisionnement

Le `Vagrantfile` n'installe rien.

```
   Vagrantfile qui provisionne Docker
        -> install.sh trouve Docker deja la
        -> on ne saura JAMAIS s'il sait l'installer

   Vagrantfile qui ne provisionne rien
        -> install.sh doit se debrouiller
        -> on teste ce que health.pdf exige
```

Provisionner Docker depuis le `Vagrantfile` masquerait un défaut du script au lieu de le révéler. La VM doit être aussi nue que la machine du correcteur.

---

## Prérequis sur la machine hôte

- **VirtualBox** 7.x (une 6.1.x convient)
- **Vagrant** 2.4.x
- **20 Go** d'espace disque libre
- Les ports `80`, `443`, `8000` et `8443` libres

> ⚠️ VirtualBox et Hyper-V (utilisé par Docker Desktop via WSL 2) se disputent l'accès au processeur. Depuis VirtualBox 7 la cohabitation fonctionne, mais si `vagrant up` échoue sur `VERR_NEM`, `raw-mode is unavailable` ou `VT-x is not available`, c'est ce conflit. Le corriger imposerait de désactiver Hyper-V, donc de casser Docker Desktop : **mieux vaut renoncer à la VM que casser l'environnement de travail**.

---

## Procédure

### 1. Libérer les ports

La pile Docker locale occupe les mêmes ports que la VM.

```
cd 5SEC1AL_2025-2026_Projet_Groupe31_ThemeHospital
docker compose down
```

`down` sans `-v` : aucune donnée n'est perdue.

### 2. Créer et démarrer la VM

```
vagrant up
vagrant ssh
```

Compter 5 à 10 minutes au premier lancement (téléchargement de la box, ~1,5 Go).

### 3. Montrer que la machine est vierge

```
lsb_release -a
which docker
```

`lsb_release` affiche `Ubuntu 22.04.x LTS` — la distribution exacte nommée par `health.pdf`.

**`which docker` n'affiche rien.** C'est le moment le plus parlant de la démonstration.

### 4. Installer

```
cd /vagrant
./install.sh
```

Compter 10 à 20 minutes : installation de Docker depuis le dépôt officiel, puis construction des quatre images.

Points à surveiller dans la sortie :

```
[0/5] Verification des dependances...
  Installation de Docker Engine depuis le depot OFFICIEL Docker...
  Utilisateur 'vagrant' ajoute au groupe 'docker'.
[1/5] Creation de .env avec des secrets aleatoires...
[2/5] Generation des certificats...
[3/5] Construction des images et demarrage des services...
[4/5] Migrations et table de cache...
[5/5] Termine.
```

### 5. Vérifier

```
exit
```

```
vagrant ssh
cd /vagrant
docker compose ps
```

> La reconnexion SSH est nécessaire : l'appartenance au groupe `docker` n'est lue qu'à l'ouverture de session. Elle prouve aussi que l'ajout au groupe a fonctionné. Sans se reconnecter : `sudo docker compose ps`.

Attendu : quatre services `Up`, `db` en `healthy`.

### 6. Faire confiance à l'autorité locale

Les certificats sont dans le dossier partagé, donc visibles depuis l'hôte. Si `certs/ca.crt` était déjà installé, **il n'y a rien à faire** : `generate-certs.sh` conserve une autorité existante.

Sinon, depuis l'hôte, suivre la section « Trust the local certificate authority » du README principal.

### 7. Dérouler le scénario

Depuis le navigateur **de l'hôte**, ouvrir `https://localhost` et suivre la section « Usage » du README principal.

> ⚠️ Le Keycloak de la VM est **vierge**. Les comptes de développement n'y existent pas : ils vivent dans des volumes Docker de la machine hôte. Le sélecteur de clés d'accès du système proposera d'anciennes entrées `localhost` que ce Keycloak ne connaît pas. **Créer des comptes neufs**, et vérifier la ligne `Connecte :` du journal après chaque connexion.

### 8. Montrer la redirection HTTP → HTTPS

```
curl.exe -i http://localhost
```

Attendu : `HTTP/1.1 301 Moved Permanently` et `Location: https://localhost/`.

> Dans le navigateur, la bascule peut être instantanée sans qu'aucune requête ne parte : c'est **HSTS**, le navigateur ayant mémorisé que ce domaine ne doit jamais être contacté en clair. Deux défenses au lieu d'une — mais moins visible. `curl` ignore HSTS et montre le `301` émis par nginx.

---

## Arrêt et nettoyage

| Action | Commande |
|---|---|
| Éteindre, VM conservée | `vagrant halt` |
| Supprimer la VM (libère plusieurs Go) | `vagrant destroy -f` puis supprimer `.vagrant/` |
| Supprimer la box téléchargée (~1,5 Go) | `vagrant box remove bento/ubuntu-22.04` |
| Reprendre l'environnement de travail | `docker compose up -d` |

**Conserver la box** si une démonstration est prévue : un futur `vagrant up` repart en deux minutes, sans dépendre du réseau. La VM, elle, se reconstruit toute seule.

Le `Vagrantfile` reste versionné : c'est lui, le livrable. Détruire la VM ne détruit rien.

---

## Ce que la VM a trouvé

Première exécution d'`install.sh` sur la VM. Docker installé correctement depuis le dépôt officiel, signatures vérifiées, puis :

```
[3/5] Construction des images et demarrage des services...
permission denied while trying to connect to the docker API
at unix:///var/run/docker.sock
```

**Cause.** Le socket `/var/run/docker.sock` appartient au groupe `docker`, créé par l'installation. L'utilisateur n'y est pas.

**Le piège dans le piège.** L'appartenance à un groupe n'est prise en compte qu'à la **prochaine ouverture de session**. Ajouter l'utilisateur au groupe ne débloque pas le script en cours d'exécution.

**Pourquoi la machine de développement ne pouvait pas le voir.** Sous Windows, Docker Desktop donne l'accès dès l'installation. Le problème n'apparaît que sur une Linux où Docker vient d'être installé — c'est-à-dire exactement le cas décrit par `health.pdf`.

**Correctif.** Une sonde de l'accès au démon, après installation :

```bash
DOCKER="docker"
if ! docker info > /dev/null 2>&1; then
    $SUDO groupadd -f docker
    $SUDO usermod -aG docker "$USER"
    DOCKER="$SUDO docker"
fi
```

Puis `$DOCKER compose ...` pour les appels du script. Deux effets à la fois : l'utilisateur est ajouté au groupe pour ses commandes futures, et le script en cours passe par `sudo`. Sur une machine où Docker est déjà accessible, `docker info` réussit et le bloc est ignoré — aucun changement de comportement.

> ⚠️ Appartenir au groupe `docker` **équivaut à un accès root** sur la machine : on peut monter n'importe quel répertoire de l'hôte dans un conteneur privilégié. C'est une commodité de développement, pas une configuration de production.

---

## Notes de configuration

**Ports identiques hôte et invité.** `frontend/src/config.js` et les URI de redirection du client Keycloak désignent explicitement `https://localhost`, `https://localhost:8000` et `https://localhost:8443`. Un port différent côté hôte casserait la redirection OIDC et la politique CORS.

**`host_ip: "127.0.0.1"`.** La VM n'est joignable que depuis la machine hôte, jamais depuis le réseau local.

**WebAuthn et contexte sécurisé.** WebAuthn exige un contexte sécurisé. Grâce à la redirection de ports, le navigateur de l'hôte voit `localhost` — contexte valide. Une démonstration passant par l'IP de la VM en réseau privé serait refusée par le navigateur.

**Clé SSH.** Vagrant remplace automatiquement sa clé publique par défaut — connue de tous — par une paire générée pour cette VM. Même principe que les secrets aléatoires d'`install.sh` : une clé partagée entre deux installations n'est plus une clé.