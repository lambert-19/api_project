# Guide d'utilisation

API de gestion de bibliothèque en ligne — Oracle · FastAPI · SQLAlchemy · Alembic

Ce guide explique comment installer, lancer et utiliser le projet au quotidien. Chaque procédure indique les commandes à taper et le **résultat attendu**, pour savoir si tout s'est bien passé.

Toutes les commandes se tapent dans un terminal **PowerShell**, à la racine du projet.

---

## Sommaire

1. [Première installation](#1-première-installation)
2. [Démarrer et arrêter le projet](#2-démarrer-et-arrêter-le-projet)
3. [Lancer l'API](#3-lancer-lapi)
4. [Explorer la base avec CloudBeaver](#4-explorer-la-base-avec-cloudbeaver)
5. [Modifier la structure de la base (migrations)](#5-modifier-la-structure-de-la-base-migrations)
6. [Administrer la sécurité](#6-administrer-la-sécurité)
7. [Réinitialiser la base](#7-réinitialiser-la-base)
8. [Dépannage](#8-dépannage)
9. [Aide-mémoire des commandes](#9-aide-mémoire-des-commandes)
10. [Annexe : comment ça marche](#10-annexe--comment-ça-marche)

---

## 1. Première installation

À faire **une seule fois**, sur chaque nouvelle machine.

### 1.1 Installer les outils

| Outil | Rôle | Vérification |
|---|---|---|
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Fait tourner Oracle, CloudBeaver et l'API | `docker --version` |
| [uv](https://docs.astral.sh/uv/) | Gère Python et les dépendances | `uv --version` |

Docker Desktop doit être **lancé** (icône de baleine verte, « Engine running ») avant toute commande `docker`.

### 1.2 Créer le fichier de configuration

```powershell
Copy-Item .env.example .env
```

Ouvrir `.env` et remplacer toutes les valeurs `changeme_...` :

| Variable | À mettre |
|---|---|
| `ORACLE_PASSWORD` | Mot de passe administrateur Oracle (SYS / SYSTEM) |
| `APP_USER_PASSWORD` | Mot de passe du propriétaire des tables (`biblio`) |
| `API_USER_PASSWORD` | Mot de passe de l'utilisateur de l'API (`biblio_api`) |
| `SECRET_KEY` | Clé de signature des jetons. Générer avec : `python -c "import secrets; print(secrets.token_hex(32))"` |

> ⚠️ **Règles pour les mots de passe** : pas de caractères `@`, `:` ou `/`. Les choisir **avant** le premier démarrage : ils sont enregistrés dans la base à sa création et ne changent plus ensuite (voir [6.4](#64-changer-un-mot-de-passe)).

> ⚠️ Le fichier `.env` contient des secrets : il ne doit **jamais** être envoyé sur Git (il est déjà dans `.gitignore`).

### 1.3 Installer les dépendances Python

```powershell
uv sync
```

**Résultat attendu :** un dossier `.venv` est créé, sans erreur.

### 1.4 Premier démarrage de la base

```powershell
docker compose up -d
```

Le premier lancement télécharge les images (environ 1,5 Go) puis crée la base. Suivre la progression :

```powershell
docker compose logs -f oracle
```

**Résultat attendu :** après 1 à 2 minutes, les lignes suivantes apparaissent (quitter avec `Ctrl+C`) :

```
CONTAINER: running /container-entrypoint-initdb.d/01-securite.sh ...
CONTAINER: DONE: running /container-entrypoint-initdb.d/01-securite.sh
DATABASE IS READY TO USE!
```

### 1.5 Créer les tables

```powershell
uv run alembic upgrade head
```

**Résultat attendu :** des lignes `INFO [alembic.runtime.migration] Running upgrade ...` sans erreur.

✅ **L'installation est terminée.** Passer à [3. Lancer l'API](#3-lancer-lapi).

---

## 2. Démarrer et arrêter le projet

### 2.1 Démarrer

```powershell
docker compose up -d
```

Démarre Oracle et CloudBeaver. Les données de la session précédente sont conservées.

### 2.2 Vérifier que tout tourne

```powershell
docker compose ps
```

**Résultat attendu :**

```
NAME                       STATUS                   PORTS
bibliotheque-cloudbeaver   Up 2 minutes             127.0.0.1:8978->8978/tcp
bibliotheque-oracle        Up 2 minutes (healthy)   127.0.0.1:1521->1521/tcp
```

La base est utilisable quand elle affiche **`(healthy)`**. Si elle affiche `(health: starting)`, attendre encore un peu.

### 2.3 Arrêter

```powershell
docker compose --profile api stop
```

Arrête tous les conteneurs **sans rien supprimer**. Au prochain `docker compose up -d`, tout redémarre avec les mêmes données.

---

## 3. Lancer l'API

Deux façons de lancer l'API. **Ne pas utiliser les deux en même temps** : elles utilisent le même port (8000).

### 3.1 Mode développement (recommandé pour coder)

```powershell
uv run fastapi dev src/main.py
```

- L'API redémarre toute seule à chaque modification d'un fichier `.py`.
- Les erreurs s'affichent directement dans le terminal.
- Arrêter avec `Ctrl+C`.

> Penser à appliquer les migrations avant (`uv run alembic upgrade head`) si les modèles ont changé.

### 3.2 Mode Docker (comme en production)

```powershell
docker compose --profile api up -d --build
```

Ce qui se passe automatiquement :

1. Construction de l'image de l'API.
2. Le conteneur `migrate` applique les migrations, puis s'arrête.
3. Le conteneur `api` démarre (seulement si les migrations ont réussi).

**Vérifier :**

```powershell
docker compose --profile api ps
```

`bibliotheque-api` doit être `(healthy)`. `bibliotheque-migrate` n'apparaît pas dans la liste : c'est normal, il a terminé son travail.

**Voir les journaux :**

```powershell
docker compose logs -f api        # journaux de l'API
docker compose logs migrate       # résultat des migrations
```

Pour arrêter uniquement l'API Docker (par exemple pour repasser en mode développement) :

```powershell
docker compose stop api
```

### 3.3 Utiliser l'API

| Adresse | Contenu |
|---|---|
| http://127.0.0.1:8000/docs | **Documentation interactive (Swagger)** : liste des routes, bouton *Try it out* pour les tester |
| http://127.0.0.1:8000/redoc | Documentation en lecture seule |
| http://127.0.0.1:8000/health | État de l'API et de la base |
| http://127.0.0.1:8000/v1/... | **Routes de l'API** : toutes préfixées par `/v1` (ex. http://127.0.0.1:8000/v1/books) |
| http://127.0.0.1:8000/v1/admin/... | Routes de gestion (inventaire, retards, export CSV), réservées aux administrateurs |

> Une ancienne URL sans `/v1` (ex. `/books`) répond `404 Route introuvable`.

**Tester que tout fonctionne :** ouvrir http://127.0.0.1:8000/health.

| Réponse | Signification |
|---|---|
| `{"status":"ok","database":"ok"}` | Tout fonctionne |
| `503 Base de données injoignable` | L'API tourne mais Oracle ne répond pas : voir [2.2](#22-vérifier-que-tout-tourne) |
| La page ne s'ouvre pas | L'API n'est pas lancée |

### 3.4 Se connecter dans Swagger

1. Ouvrir http://127.0.0.1:8000/docs et cliquer sur **Authorize** (cadenas en haut à droite).
2. Remplir **username** (l'email) et **password**.
3. **Scopes** : ne rien cocher pour recevoir toutes les permissions de son rôle. Cocher seulement certaines cases pour obtenir un jeton restreint (par exemple `profil` seul : lecture seule).
4. Cliquer **Authorize**, puis **Close**. Le jeton est envoyé automatiquement à chaque *Try it out*.

| Permission | Membre | Admin | Routes |
|---|:---:|:---:|---|
| `profil` | ✅ | ✅ | `/v1/users/me`, `/v1/users/me/loans`, `/v1/users/me/history` |
| `emprunts` | ✅ | ✅ | `POST /v1/loans`, `POST /v1/loans/{id}/return` |
| `livres:ecrire` | ❌ | ✅ | `POST`, `PATCH`, `DELETE /v1/admin/books`, `PUT`, `DELETE /v1/admin/books/{id}/cover` |
| `emprunts:gerer` | ❌ | ✅ | `GET /v1/admin/loans/overdue`, retour de l'emprunt d'un autre |

Une réponse `403 Permission insuffisante : … requis` signifie que le jeton n'a pas la permission : se reconnecter sans restreindre les cases, ou avec un compte administrateur.

> En cas de problème, chaque réponse contient un en-tête **`X-Request-ID`** (visible dans *Response headers* de Swagger). Le communiquer permet de retrouver la ligne correspondante dans les journaux du serveur.

---

## 4. Explorer la base avec CloudBeaver

CloudBeaver est une interface web pour voir les tables, leur contenu, et exécuter du SQL.

**Adresse :** http://127.0.0.1:8978

### 4.1 Première configuration (une seule fois)

1. Ouvrir http://127.0.0.1:8978.
2. L'assistant *Initial Server Configuration* s'affiche : cliquer **Next**.
3. Choisir un identifiant et un mot de passe **administrateur CloudBeaver** (ce compte sert seulement à se connecter à CloudBeaver, il n'a rien à voir avec Oracle).
4. Terminer l'assistant et se connecter avec ce compte.

### 4.2 Ajouter la connexion à la base

1. Cliquer sur **New Connection** (icône `+` en haut à gauche).
2. Choisir **Oracle**.
3. Remplir :

   | Champ | Valeur |
   |---|---|
   | Host | `oracle` |
   | Port | `1521` |
   | Database | `FREEPDB1` — choisir le type **Service** (pas SID) |
   | User | valeur de `APP_USER` dans `.env` (ex. `biblio`) |
   | Password | valeur de `APP_USER_PASSWORD` |

4. Cliquer **Test** → *Connected* doit s'afficher.
5. Cliquer **Create**.

> Le Host est bien `oracle` et **pas** `localhost` : CloudBeaver tourne dans son propre conteneur et joint Oracle par le réseau Docker.

### 4.3 Consulter les tables

Dans l'arbre à gauche : **connexion → Schemas → BIBLIO → Tables**. Double-cliquer sur une table puis ouvrir l'onglet **Data** pour voir son contenu.

### 4.4 Exécuter du SQL

Sélectionner la connexion, puis **SQL** (en haut) → écrire la requête → `Ctrl+Entrée`.

### 4.5 Connexion administrateur (optionnelle)

Pour les tâches d'administration (audit, déverrouillage de comptes), créer une seconde connexion avec les mêmes paramètres mais :

| Champ | Valeur |
|---|---|
| User | `SYSTEM` |
| Password | valeur de `ORACLE_PASSWORD` |

---

## 5. Modifier la structure de la base (migrations)

On ne crée ni ne modifie **jamais** une table à la main dans CloudBeaver. Toute modification passe par Alembic, pour qu'elle soit enregistrée, reproductible chez le binôme, et annulable.

### 5.1 Ajouter ou modifier une table

1. **Modifier le modèle** dans `src/models/` (ex. ajouter une colonne dans `livre.py`).
2. **Si c'est un nouveau fichier de modèle**, l'importer dans [src/models/\_\_init\_\_.py](../src/models/__init__.py). Sinon Alembic ne le voit pas.
3. **Générer la migration :**
   ```powershell
   uv run alembic revision --autogenerate -m "ajout colonne isbn"
   ```
   **Résultat attendu :** `Generating ...\alembic\versions\2026_..._ajout_colonne_isbn.py ... done`
4. **Relire le fichier généré** dans `alembic/versions/`. Alembic peut se tromper (par exemple, un renommage de colonne apparaît comme une suppression + un ajout, ce qui perd les données).
5. **Appliquer :**
   ```powershell
   uv run alembic upgrade head
   ```
6. **Vérifier** dans CloudBeaver (clic droit sur *Tables* → **Refresh**).
7. **Committer** le modèle *et* le fichier de migration ensemble.

Les droits de l'API sur les nouvelles tables sont donnés **automatiquement** à l'étape 5 : rien à faire.

### 5.2 Récupérer les migrations du binôme

Après un `git pull` qui contient de nouveaux fichiers dans `alembic/versions/` :

```powershell
uv run alembic upgrade head
```

### 5.3 Annuler la dernière migration

```powershell
uv run alembic downgrade -1
```

> ⚠️ Annuler une migration qui a créé une table **supprime la table et ses données**.

### 5.4 Savoir où on en est

```powershell
uv run alembic current     # migration actuellement appliquée
uv run alembic history     # liste de toutes les migrations
```

---

## 6. Administrer la sécurité

### 6.1 Les comptes Oracle

| Compte | Utilisé par | Peut faire |
|---|---|---|
| `SYS` / `SYSTEM` | Administration uniquement | Tout |
| `BIBLIO` | Alembic, CloudBeaver | Créer et modifier les tables (quota 100 Mo) |
| `BIBLIO_API` | L'API | Lire et écrire des données **uniquement** (pas de `CREATE`, `DROP`, `ALTER`) |

Règles appliquées aux deux comptes applicatifs :

- **5 mots de passe erronés** d'affilée → compte **verrouillé 15 minutes**.
- Impossible de réutiliser un des 5 derniers mots de passe.

### 6.2 Consulter le journal d'audit

Sont enregistrés : les échecs de connexion (tous comptes) et les modifications de structure (`CREATE`, `ALTER`, `DROP`, `TRUNCATE`, `GRANT`, `REVOKE`) faites par `BIBLIO` et `BIBLIO_API`.

Dans CloudBeaver, avec la connexion **SYSTEM** ([4.5](#45-connexion-administrateur-optionnelle)) :

```sql
SELECT event_timestamp, dbusername, action_name, return_code
FROM unified_audit_trail
WHERE unified_audit_policies LIKE '%BIBLIO%'
ORDER BY event_timestamp DESC;
```

`return_code = 0` : action réussie. Sinon, c'est le code d'erreur Oracle (ex. `1017` = mauvais mot de passe).

### 6.3 Déverrouiller un compte

Symptôme : `ORA-28000: the account is locked`. Attendre 15 minutes, ou, connecté en **SYSTEM** :

```sql
ALTER USER biblio_api ACCOUNT UNLOCK;
```

### 6.4 Changer un mot de passe

Modifier `.env` ne suffit pas : Oracle garde l'ancien mot de passe. Il faut le changer **aux deux endroits**.

1. Dans CloudBeaver, connecté en **SYSTEM** :
   ```sql
   ALTER USER biblio_api IDENTIFIED BY "NouveauMotDePasse";
   ```
2. Mettre la même valeur dans `.env` (`API_USER_PASSWORD`).
3. Relancer l'API.

(Même principe pour `biblio` avec `APP_USER_PASSWORD`. Penser aussi à mettre à jour la connexion CloudBeaver.)

### 6.5 Vérifier les droits des comptes

Connecté en **SYSTEM** :

```sql
SELECT grantee, privilege FROM dba_sys_privs WHERE grantee IN ('BIBLIO', 'BIBLIO_API')
UNION ALL
SELECT grantee, granted_role FROM dba_role_privs WHERE grantee IN ('BIBLIO', 'BIBLIO_API');
```

---

## 7. Réinitialiser la base

Pour repartir d'une base neuve (après un changement de mots de passe dans `.env`, ou si la base est dans un état incohérent).

> ⚠️ **Supprime toutes les données** de la base, ainsi que la configuration de CloudBeaver.

```powershell
docker compose --profile api down -v
docker compose up -d
docker compose logs -f oracle          # attendre "DATABASE IS READY TO USE!"
uv run alembic upgrade head            # recréer les tables
```

Puis refaire la configuration de CloudBeaver ([4.1](#41-première-configuration-une-seule-fois) et [4.2](#42-ajouter-la-connexion-à-la-base)).

---

## 8. Dépannage

| Symptôme | Cause | Solution |
|---|---|---|
| `failed to connect to the docker API` | Docker Desktop n'est pas lancé | Lancer Docker Desktop, attendre « Engine running » |
| Une page ou une connexion **charge à l'infini** avec `localhost` | Sous Windows, `localhost` passe par IPv6, mal géré par Docker | Utiliser `127.0.0.1` à la place (dans le navigateur et dans `.env`) |
| `ORA-01017: invalid credential` | Mot de passe de `.env` différent de celui enregistré dans la base | Voir [6.4](#64-changer-un-mot-de-passe) ou [7](#7-réinitialiser-la-base) |
| `ORA-28000: the account is locked` | 5 échecs de connexion | Voir [6.3](#63-déverrouiller-un-compte) |
| `ORA-01031: insufficient privileges` depuis l'API | L'API tente de modifier la structure | Normal : passer par une migration ([5](#5-modifier-la-structure-de-la-base-migrations)) |
| `ORA-00942: table or view does not exist` | Migrations pas appliquées | `uv run alembic upgrade head` |
| `address already in use` / port 8000 occupé | L'API tourne déjà (en Docker ou dans un autre terminal) | `docker compose stop api` ou fermer l'autre terminal |
| `bibliotheque-api` ne démarre pas | Les migrations ont échoué | `docker compose logs migrate` |
| `validation error for Settings ... Field required` | Variable manquante dans `.env` | Comparer `.env` avec `.env.example` |
| `APP_USER manquant dans .env` (Docker) | Idem | Idem |
| Script d'initialisation : `$'\r': command not found` | Le fichier `.sh` a des fins de ligne Windows | Dans VS Code, ouvrir le fichier, cliquer sur `CRLF` en bas à droite → `LF`, enregistrer, puis [7](#7-réinitialiser-la-base) |
| Alembic ne détecte pas une nouvelle table | Modèle non importé | L'ajouter dans `src/models/__init__.py` |

---

## 9. Aide-mémoire des commandes

| Je veux… | Commande |
|---|---|
| Démarrer la base et CloudBeaver | `docker compose up -d` |
| Voir l'état des conteneurs | `docker compose --profile api ps` |
| Tout arrêter (sans rien perdre) | `docker compose --profile api stop` |
| Lancer l'API en développement | `uv run fastapi dev src/main.py` |
| Lancer l'API dans Docker | `docker compose --profile api up -d --build` |
| Arrêter l'API Docker | `docker compose stop api` |
| Voir les journaux | `docker compose logs -f oracle` / `api` / `migrate` |
| Appliquer les migrations | `uv run alembic upgrade head` |
| Créer une migration | `uv run alembic revision --autogenerate -m "description"` |
| Annuler la dernière migration | `uv run alembic downgrade -1` |
| Voir la migration actuelle | `uv run alembic current` |
| Réinstaller les dépendances | `uv sync` |
| Tout réinitialiser (⚠️ efface les données) | `docker compose --profile api down -v` |

| Adresse | Service |
|---|---|
| http://127.0.0.1:8000/docs | Documentation interactive de l'API |
| http://127.0.0.1:8000/health | État de l'API |
| http://127.0.0.1:8978 | CloudBeaver |
| `127.0.0.1:1521/FREEPDB1` | Oracle (pour un client SQL externe) |

---

## 10. Annexe : comment ça marche

Pour comprendre ce qui se passe derrière les commandes ci-dessus.

### 10.1 Les conteneurs

```
  Navigateur ──► 127.0.0.1:8000          127.0.0.1:8978 ◄── Navigateur
                      │                         │
  ┌─────────────── Réseau Docker ───────────────┼──────────────┐
  │                   ▼                         ▼              │
  │  ┌──────────┐  ┌──────────┐          ┌─────────────┐       │
  │  │ migrate  │  │   api    │          │ cloudbeaver │       │
  │  └────┬─────┘  └────┬─────┘          └──────┬──────┘       │
  │       │ BIBLIO      │ BIBLIO_API            │ BIBLIO       │
  │       ▼             ▼                       ▼              │
  │  ┌─────────────────────────────────────────────────┐       │
  │  │        oracle — base FREEPDB1, schéma BIBLIO     │       │
  │  └─────────────────────────────────────────────────┘       │
  │                 volume oracle-data (données)               │
  └────────────────────────────────────────────────────────────┘
```

| Conteneur | Rôle | Durée de vie |
|---|---|---|
| `oracle` | La base de données | Permanent |
| `cloudbeaver` | Interface web | Permanent |
| `migrate` | Applique les migrations | Démarre, travaille, s'arrête |
| `api` | L'API FastAPI | Permanent |

Les ports n'écoutent que sur `127.0.0.1` : rien n'est accessible depuis le réseau local.

### 10.2 Qui reçoit quel secret

| Variable | `oracle` | `migrate` | `api` |
|---|:---:|:---:|:---:|
| `ORACLE_PASSWORD` | ✅ | ❌ | ❌ |
| `APP_USER_PASSWORD` | ✅ | ✅ | ❌ |
| `API_USER_PASSWORD` | ✅ | ❌ | ✅ |
| `SECRET_KEY` | ❌ | ❌ | ✅ |

Si l'API était compromise, l'attaquant ne trouverait ni le mot de passe administrateur, ni celui du propriétaire des tables. En Python, la même séparation existe : `Settings` (API) et `MigrationSettings` (Alembic) dans [src/config.py](../src/config.py).

### 10.3 Au premier démarrage d'Oracle

L'image crée la base et l'utilisateur `BIBLIO`, puis exécute [docker/oracle/initdb/01-securite.sh](../docker/oracle/initdb/01-securite.sh) :

1. Crée le profil de mots de passe (verrouillage, non-réutilisation).
2. Réduit les droits de `BIBLIO` au strict nécessaire pour les migrations.
3. Crée le rôle `BIBLIO_API_ROLE` (vide pour l'instant).
4. Crée `BIBLIO_API` avec seulement la connexion et ce rôle.
5. Active l'audit.

Aux démarrages suivants, rien de tout cela n'est rejoué : c'est pourquoi modifier `.env` après coup ne change pas les mots de passe dans Oracle.

### 10.4 Pendant une migration

`alembic upgrade head` se connecte en `BIBLIO`, applique les migrations manquantes (la table `ALEMBIC_VERSION` mémorise la dernière appliquée), puis [alembic/env.py](../alembic/env.py) exécute pour chaque table :

```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON <table> TO BIBLIO_API_ROLE
```

C'est ce qui donne automatiquement à l'API l'accès aux nouvelles tables.

### 10.5 Pendant une requête HTTP

1. FastAPI voit `Depends(get_db)` dans la route et appelle `get_db()` ([src/database.py](../src/database.py)), qui crée une session.
2. La session emprunte une connexion au **pool** (des connexions gardées ouvertes pour aller plus vite). À la création d'une nouvelle connexion, `ALTER SESSION SET CURRENT_SCHEMA = BIBLIO` est exécuté : l'API écrit `livre` au lieu de `BIBLIO.livre`, mais garde les droits limités de `BIBLIO_API`.
3. La route s'exécute et renvoie sa réponse.
4. Le bloc `finally` de `get_db()` ferme la session et rend la connexion au pool, **même en cas d'erreur**.
