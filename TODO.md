# TODO – Projet 5BDDD : Système de gestion de bibliothèque en ligne

Stack imposée : **Oracle + Python + FastAPI + SQLAlchemy + Alembic + Pydantic**

---

## Phase 0 : Mise en place
- [x] Installer les dépendances : `uv add "fastapi[standard]" sqlalchemy alembic oracledb pydantic-settings "pwdlib[argon2]" pyjwt`
- [x] **Docker Compose** : créer un `docker-compose.yml` pour la base Oracle
  - [x] Service `oracle` avec l'image `gvenzl/oracle-free` (ou `gvenzl/oracle-xe`), port `1521:1521`
  - [x] Variables lues depuis `.env` : `ORACLE_PASSWORD`, `APP_USER`, `APP_USER_PASSWORD` (l'image crée automatiquement l'utilisateur applicatif)
  - [x] Volume nommé (ex. `oracle-data:/opt/oracle/oradata`) pour conserver les données entre les redémarrages
  - [x] `healthcheck` (l'image fournit `healthcheck.sh`) pour savoir quand la base est prête
  - [x] Script d'initialisation `docker/oracle/initdb/01-securite.sh` monté dans `/container-entrypoint-initdb.d` :
    - [x] `BIBLIO` (propriétaire, Alembic) : `DB_DEVELOPER_ROLE` retiré, droits minimaux (SESSION, TABLE, SEQUENCE, VIEW), quota 100 Mo
    - [x] `BIBLIO_API` (API) : connexion + rôle `BIBLIO_API_ROLE` uniquement (vérifié : `CREATE TABLE` refusé)
    - [x] Profil `BIBLIO_PROFILE` : verrouillage après 5 échecs (15 min), pas de réutilisation des mots de passe
    - [x] Audit unifié : échecs de connexion (tous utilisateurs) et DDL/GRANT de BIBLIO et BIBLIO_API
  - [x] (Bonus) Service `api` (Dockerfile de l'app FastAPI) avec `depends_on: oracle: condition: service_healthy`
    - [x] Image `uv` multi-couches, utilisateur non-root, healthcheck sur `/health`, `.env` jamais copié dans l'image
    - [x] Profil Compose `api` : `docker compose --profile api up -d --build`
    - [x] Service `migrate` (`alembic upgrade head`, s'exécute une fois) ; `api` démarre après sa réussite
    - [x] L'API ne reçoit que ses variables (ni `ORACLE_PASSWORD` ni `APP_USER_PASSWORD`)
  - [x] Tester : `docker compose up -d`, `docker compose ps` (statut *healthy*), `docker compose logs -f oracle`
  - [x] Service `cloudbeaver` : interface web pour explorer la base sur http://localhost:8978
- [x] Vérifier que l'utilisateur/schéma Oracle de l'application a des droits limités (partie « base sécurisée », ne pas utiliser SYSTEM)
- [x] `config.py` : `database_url` (BIBLIO_API, pour l'API) et `migration_url` (BIBLIO, pour Alembic)
- [x] Fichier `.env` (identifiants Oracle, URL de la base, clé secrète JWT) lu par `pydantic-settings` et par Docker Compose, `.env` ajouté au `.gitignore`, avec un `.env.example` versionné
- [x] Organiser le code : `src/` (main, config, database, security, dependances, exceptions), `models/`, `schemas/`, `routers/`, `services/` ; `alembic/` ; `tests/` (voir la structure dans le README)

## Phase 1 : Base de données
- [x] `database.py` : engine SQLAlchemy (`settings.database_url`) et dépendance `get_db()` construite avec `yield`
  - [x] `Base` avec convention de nommage des contraintes (pour Alembic)
  - [x] `/health` vérifie la base via `Depends(get_db)`
  - [x] À chaque connexion : `ALTER SESSION SET CURRENT_SCHEMA = BIBLIO` (les tables appartiennent à BIBLIO, pas à BIBLIO_API)
- [x] Modèles SQLAlchemy (`src/models/utilisateur.py`, `livre.py`, `emprunt.py`) :
  - [x] **Utilisateur** : id, nom, email (unique), téléphone, mot_de_passe_hash, date_inscription, rôle (admin/membre, contrainte CHECK)
  - [x] **Livre** : id, titre, auteur, date_publication, disponible (booléen), ISBN (unique), `genre` (ajouté par la 2e migration)
  - [x] **Emprunt** : id, utilisateur_id (FK), livre_id (FK), date_emprunt, date_retour_prevue, date_retour (null tant que le livre n'est pas rendu)
  - [x] Relations `relationship()`, contraintes et index (email unique, index sur titre/auteur, CHECK sur les dates)
  - [x] Index unique fonctionnel `uq_emprunt_livre_en_cours` : la base refuse deux emprunts en cours du même livre
- [x] `alembic init alembic` et configurer `env.py` avec les modèles (`target_metadata`) et `MigrationSettings.migration_url`
  - [x] `Base` déplacée dans `models/base.py` ; config séparée API (`Settings`) / migrations (`MigrationSettings`)
  - [x] Après chaque migration : `GRANT SELECT, INSERT, UPDATE, DELETE` sur toutes les tables de BIBLIO à `BIBLIO_API_ROLE`
- [x] Première migration : `alembic revision --autogenerate -m "init"` puis `alembic upgrade head`
  - [x] Relue et corrigée (contrainte CHECK du rôle générée en double par Alembic)
  - [x] Vérifiée en BIBLIO_API : double emprunt, rôle invalide, email en double refusés ; CREATE/DROP TABLE refusés (ORA-01031)
  - [x] Réversible (`downgrade base` puis `upgrade head`), `alembic check` propre (index fonctionnel exclu de la comparaison dans `env.py`)
- [x] Une **deuxième migration** qui modifie le schéma : ajout de `livre.genre` (nullable, indexé) pour montrer l'évolution avec Alembic à la soutenance
  - [x] Réversible (`downgrade -1` / `upgrade head`), recherche par genre testée

## Phase 2 : Utilisateurs et authentification
- [x] Schémas Pydantic (`src/schemas/utilisateur.py`) : `UtilisateurCreate` (`EmailStr` mis en minuscules, validation du téléphone, mot de passe 8-128 caractères), `UtilisateurOut` (sans mot de passe)
- [x] `POST /users/register` : inscription avec mot de passe hashé (Argon2), 409 si email déjà utilisé, rôle toujours `membre`
- [x] `POST /auth/token` : connexion avec **OAuth2PasswordRequestForm**, renvoie un **JWT** (même message d'erreur et même durée que l'email existe ou non)
  📖 *Doc : Tutorial → Security → « OAuth2 with Password (and hashing), Bearer with JWT tokens »*
- [x] Dépendance `get_current_user` avec `Depends(oauth2_scheme)` (`src/dependances.py`) 📖 *Doc : Dependencies*
- [x] Dépendance `get_current_admin` pour les routes réservées aux admins
- [x] `GET /users/me` : profil de l'utilisateur connecté
- [x] `GET /users/me/loans` : emprunts en cours
- [x] `GET /users/me/history` : historique des emprunts
- [x] Créer un premier administrateur : `uv run python src/creer_admin.py` (crée ou promeut)

## Phase 3 : Livres
- [x] Schémas `LivreCreate`, `LivreUpdate` (champs optionnels, titre/auteur non nuls), `LivreOut`, ISBN-10/13 validé
- [x] `POST /books` : ajout (admin), 409 si ISBN déjà utilisé
- [x] `PATCH /books/{id}` : modification (admin), impossible de remettre disponible un livre emprunté 📖 *Doc : Body – Updates (`model_dump(exclude_unset=True)`)*
- [x] `DELETE /books/{id}` : suppression (admin), refusée si le livre a un historique d'emprunts (le rendre indisponible à la place)
- [x] `GET /books/{id}` : détail, `HTTPException(404)` si introuvable
- [x] `GET /books?title=&author=&genre=&available=&skip=&limit=` : recherche insensible à la casse et pagination
  📖 *Doc : Query Parameters and String Validations (`Query(min_length=...)`)*

## Phase 4 : Emprunts
- [x] `POST /loans` (body : `livre_id`) : vérifier la disponibilité, créer l'emprunt et passer `disponible` à False, **dans une seule transaction** (`SELECT ... FOR UPDATE` sur le livre, logique dans `src/services/emprunts.py`)
  - [x] Testé : 8 emprunts simultanés du même livre → 1 seul accepté
- [x] `POST /loans/{id}/return` : renseigner `date_retour`, remettre `disponible` à True, vérifier que c'est bien l'emprunteur (ou un admin)
- [x] Codes d'erreur adaptés : 409 (livre déjà emprunté, déjà rendu, limite atteinte), 403 (pas le droit), 404 (introuvable)
- [x] (Bonus) Limite de 5 emprunts simultanés par utilisateur, `GET /loans/overdue` (retards, admin)

## Phase 5 : Fonctions FastAPI avancées (demandées par le prof)
- [x] **APIRouter** avec `prefix` et `tags` 📖 *Bigger Applications – Multiple Files*
- [x] **response_model** et **status_code** sur chaque route (201 création, 204 suppression) 📖 *Response Model*
- [x] **Lifespan events** : vérifier la connexion à la base au démarrage (l'API refuse de démarrer si Oracle est injoignable) 📖 *Advanced → Lifespan Events*
- [x] **Middleware CORS** (origines dans `CORS_ORIGINS`, méthodes et en-têtes limités) 📖 *CORS*
- [x] **Métadonnées Swagger** : titre, description, tags décrits, exemples dans les schémas (`json_schema_extra`)
  📖 *Metadata and Docs URLs, Declare Request Example Data*
- [x] **Gestionnaires d'exceptions** personnalisés : erreurs métier (`src/exceptions.py`) et erreurs base (503/500 sans détail SQL) 📖 *Handling Errors*
- [x] (Bonus) **BackgroundTasks** : « envoi » d'un mail de confirmation d'emprunt (journalisé) 📖 *Background Tasks*

## Phase 6 : Tests et qualité
- [x] Tests avec **TestClient** et pytest : 36 tests (`uv run pytest`), sur la vraie base Oracle 📖 *Testing*
- [x] Remplacer `get_db` via `app.dependency_overrides` : chaque test tourne dans une transaction annulée à la fin (la base n'est jamais modifiée) 📖 *Testing Dependencies with Overrides*
- [x] Tester au minimum : inscription, connexion, emprunt d'un livre indisponible (doit échouer), retour (+ jetons expirés/falsifiés, droits admin, CORS, erreurs base)
- [x] Tests de sécurité (`tests/test_securite.py`) : force brute, injection SQL, jetons falsifiés, Argon2, droits Oracle de l'API
- [x] Limite des échecs de connexion : 5 par minute et par IP (`429`)
- [x] Vérifié : verrouillage Oracle après 5 échecs, journal d'audit, `pip-audit` sans vulnérabilité
- [x] Test de charge (`scripts/charge.py`) : ~1 000 à 1 200 req/s en lecture, ~490 req/s pour emprunt + retour, 0 erreur
  - [x] Corrigé : `ORA-12516` sous charge → pool de connexions fixe (`DB_POOL_SIZE`)
- [x] Script de seed : `uv run python src/seed.py` (3 utilisateurs dont 1 admin, 12 livres, 3 emprunts dont 1 en retard ; mot de passe `demo1234`)

## Phase 7 : Livrables et soutenance
- [x] Vérifier que `/docs` (Swagger) est complet et propre
- [x] README : routes, données de démo, tests, schéma de la base, choix techniques ; installation, copie de `.env.example` vers `.env`, `docker compose up -d`, `alembic upgrade head`, `fastapi dev`
- [x] Schéma de la base (diagramme Mermaid des 3 tables dans le README)
- [x] Préparer les **justifications des choix techniques** : JWT vs sessions, hash Argon2, utilisateur Oracle aux droits limités, transaction sur l'emprunt, séparation routers/services/schémas
- [x] Scénario de démo (répété et vérifié) : inscription → connexion → recherche → emprunt → double emprunt (erreur) → retour → historique
- [ ] Répartir le travail dans le binôme (ex. base/Alembic/modèles d'un côté, authentification/routes de l'autre)

---

**Conseil :** pour les phases 2 et 5, suivre le tutoriel officiel dans l'ordre : https://fastapi.tiangolo.com → *Learn → Tutorial – User Guide → Security*, puis *Bigger Applications*.
