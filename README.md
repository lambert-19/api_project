# API de gestion de bibliothèque en ligne

Mini-projet 5BDDD : API permettant aux utilisateurs d'emprunter et de rendre des livres, avec gestion de l'inventaire et des utilisateurs inscrits.

**Stack :** Oracle Database (Docker) · Python 3.13 · FastAPI · SQLAlchemy · Alembic · Pydantic

> Projet en cours de développement : voir l'avancement dans [TODO.md](TODO.md).
> Mode d'emploi complet (installation, utilisation, administration, dépannage) : [docs/GUIDE_UTILISATION.md](docs/GUIDE_UTILISATION.md).

## Prérequis

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (lancé)
- [uv](https://docs.astral.sh/uv/) (gestionnaire de projet Python)

## Installation

### 1. Configuration

Copier le fichier d'exemple puis modifier les valeurs :

```powershell
Copy-Item .env.example .env
```

| Variable | Rôle |
|---|---|
| `ORACLE_PASSWORD` | Mot de passe des comptes admin Oracle (`SYS`, `SYSTEM`). Utilisé uniquement par Docker. |
| `APP_USER` / `APP_USER_PASSWORD` | Propriétaire du schéma (`BIBLIO`). Crée les tables, utilisé uniquement par Alembic. |
| `API_USER` / `API_USER_PASSWORD` | Utilisateur de l'API (`BIBLIO_API`). Peut seulement lire et écrire des données. |
| `DB_HOST` / `DB_PORT` / `DB_SERVICE` | Connexion de l'API à Oracle (`127.0.0.1`, `1521`, `FREEPDB1`). |
| `SECRET_KEY` | Clé de signature des jetons JWT. Générer avec `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Durée de validité d'un jeton. |

Éviter les caractères `@ : /` dans les mots de passe.

### 2. Base de données Oracle

```powershell
docker compose up -d
docker compose ps        # attendre le statut "healthy" (1 à 2 min au premier lancement)
```

À la première initialisation, le script [docker/oracle/initdb/01-securite.sh](docker/oracle/initdb/01-securite.sh) crée les utilisateurs, le rôle, le profil de mots de passe et les règles d'audit (voir [Sécurité de la base](#sécurité-de-la-base)).

Les mots de passe et ce script ne s'appliquent qu'à la première initialisation. Pour repartir de zéro (**supprime toutes les données**) :

```powershell
docker compose down -v
docker compose up -d
```

### 3. Dépendances Python

```powershell
uv sync
```

## Migrations (Alembic)

Les migrations s'exécutent avec le propriétaire du schéma (`BIBLIO`). Après chaque migration, [alembic/env.py](alembic/env.py) donne automatiquement à `BIBLIO_API_ROLE` les droits `SELECT`, `INSERT`, `UPDATE`, `DELETE` sur toutes les tables.

```powershell
uv run alembic upgrade head                                   # appliquer les migrations
uv run alembic revision --autogenerate -m "description"       # créer une migration après modification des modèles
uv run alembic downgrade -1                                   # annuler la dernière migration
uv run alembic current                                        # version actuelle de la base
```

Tout nouveau modèle doit être importé dans [src/models/\_\_init\_\_.py](src/models/__init__.py), sinon `--autogenerate` ne le voit pas. Toujours relire le fichier généré avant de l'appliquer.

## Lancer l'API

**En développement** (rechargement automatique à chaque modification) :

```powershell
uv run fastapi dev src/main.py
```

**Dans Docker** (comme en production) :

```powershell
docker compose --profile api up -d --build
```

Le service `migrate` applique d'abord les migrations puis s'arrête ; l'API ne démarre que s'il a réussi (`docker compose logs migrate` en cas de problème).

Dans les deux cas, l'API est sur **http://127.0.0.1:8000** et la documentation Swagger sur **http://127.0.0.1:8000/docs**. Ne pas lancer les deux en même temps : ils utilisent le même port.

Le service `api` est dans un profil Compose : un simple `docker compose up -d` ne lance que la base et CloudBeaver.

## Interface d'administration (CloudBeaver)

Une interface web pour explorer la base est disponible sur **http://127.0.0.1:8978**.

Au premier lancement, créer un compte admin CloudBeaver, puis une connexion **Oracle** :

| Champ | Valeur |
|---|---|
| Host | `oracle` (nom du service Docker, pas `localhost`) |
| Port | `1521` |
| Database | `FREEPDB1` (type **Service**) |
| User / Password | `APP_USER` / `APP_USER_PASSWORD` du `.env` (pour voir et gérer les tables) |

Pour consulter le journal d'audit, créer une seconde connexion avec `SYSTEM` / `ORACLE_PASSWORD`.

## Sécurité de la base

Principe du **moindre privilège** : chaque compte n'a que les droits dont il a besoin.

| Compte | Utilisé par | Droits |
|---|---|---|
| `SYS` / `SYSTEM` | Administration uniquement | Tous. Mot de passe inconnu de l'API. |
| `BIBLIO` | Alembic (migrations) | Connexion, création de tables, séquences et vues. Quota de 100 Mo. |
| `BIBLIO_API` | L'API FastAPI | Connexion et rôle `BIBLIO_API_ROLE` : `SELECT`, `INSERT`, `UPDATE`, `DELETE` sur les tables de `BIBLIO`. Aucun `CREATE`, `DROP` ou `ALTER`. |

- **Profil `BIBLIO_PROFILE`** (appliqué aux deux comptes) : compte verrouillé 15 minutes après 5 échecs de connexion, impossible de réutiliser les 5 derniers mots de passe. Pas d'expiration, pour ne pas bloquer l'API en production.
- **Audit unifié** : les échecs de connexion de tous les comptes, et les modifications de schéma (`CREATE`, `ALTER`, `DROP`, `TRUNCATE`, `GRANT`, `REVOKE`) de `BIBLIO` et `BIBLIO_API`, sont journalisés. Consultation, connecté en `SYSTEM` :

  ```sql
  SELECT event_timestamp, dbusername, action_name, return_code
  FROM unified_audit_trail
  WHERE unified_audit_policies LIKE '%BIBLIO%'
  ORDER BY event_timestamp DESC;
  ```

## Structure du projet

```
.
├── docker-compose.yml          # Oracle + CloudBeaver + migrate + API (profil "api")
├── Dockerfile                  # image de l'API (et des migrations)
├── docker/oracle/initdb/
│   └── 01-securite.sh          # utilisateurs, rôle, profil, audit (1re initialisation)
├── alembic.ini
├── alembic/
│   ├── env.py                  # connexion en BIBLIO + GRANT automatiques
│   └── versions/               # fichiers de migration
├── .env.example                # modèle de configuration
├── pyproject.toml              # dépendances (uv)
└── src/
    ├── main.py                 # application FastAPI
    ├── config.py               # Settings (API) et MigrationSettings (Alembic)
    ├── database.py             # connexion SQLAlchemy de l'API, get_db()
    └── models/
        ├── __init__.py         # importe tous les modèles (pour Alembic)
        └── base.py             # Base des modèles, convention de nommage
```

## Choix techniques

- **Deux utilisateurs Oracle séparés** : si l'API était compromise, l'attaquant pourrait lire et modifier des données, mais pas supprimer ou modifier les tables. Voir [Sécurité de la base](#sécurité-de-la-base).
- **Mot de passe du propriétaire isolé** : seul Alembic le lit (`MigrationSettings`). La config de l'API (`Settings`) ne le contient pas, et dans Docker le conteneur `api` ne le reçoit pas : seul le conteneur éphémère `migrate` l'a.
- **Ports liés à `127.0.0.1`** : Oracle et CloudBeaver ne sont pas exposés sur le réseau local.
- **Secrets hors du code** : configuration dans `.env` (non versionné), mots de passe typés `SecretStr` pour ne jamais apparaître dans les logs.
- **Volume Docker** : les données Oracle survivent aux redémarrages du conteneur.
- **Image de l'API durcie** : exécutée avec un utilisateur non-root, `.env` exclu de l'image (les secrets sont injectés au lancement), dépendances figées par `uv.lock`.

## Dépannage

- **La page ou la connexion charge à l'infini avec `localhost`** : sous Windows, `localhost` passe d'abord par IPv6. Utiliser `127.0.0.1`.
- **`docker compose` : failed to connect to the docker API** : Docker Desktop n'est pas lancé.
- **Connexion refusée (mot de passe invalide)** : le `.env` a été modifié après la première initialisation. Voir la réinitialisation ci-dessus.
- **`ORA-28000: the account is locked`** : 5 échecs de connexion d'affilée. Attendre 15 minutes, ou déverrouiller en `SYSTEM` : `ALTER USER biblio_api ACCOUNT UNLOCK;`
- **Le script d'initialisation échoue avec `$'\r': command not found`** : le fichier `.sh` a des fins de ligne Windows. Le `.gitattributes` force LF ; sinon, le convertir en LF dans VS Code (en bas à droite, `CRLF` → `LF`).
