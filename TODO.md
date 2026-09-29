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
  - [ ] (Optionnel) Scripts SQL d'initialisation montés dans `/container-entrypoint-initdb.d` (droits, rôles)
  - [ ] (Bonus) Service `api` (Dockerfile de l'app FastAPI) avec `depends_on: oracle: condition: service_healthy`
  - [x] Tester : `docker compose up -d`, `docker compose ps` (statut *healthy*), `docker compose logs -f oracle`
  - [x] Service `cloudbeaver` : interface web pour explorer la base sur http://localhost:8978
- [ ] Vérifier que l'utilisateur/schéma Oracle de l'application a des droits limités (partie « base sécurisée », ne pas utiliser SYSTEM)
- [ ] Fichier `.env` (identifiants Oracle, URL de la base, clé secrète JWT) lu par `pydantic-settings` et par Docker Compose, `.env` ajouté au `.gitignore`, avec un `.env.example` versionné
- [ ] Organiser le code :
  ```
  src/api_project/
    main.py          # app FastAPI
    config.py        # Settings (pydantic-settings)
    database.py      # engine, SessionLocal, get_db
    models/          # SQLAlchemy : user.py, book.py, loan.py
    schemas/         # Pydantic : UserCreate, UserOut, BookCreate...
    routers/         # users.py, auth.py, books.py, loans.py
    services/        # logique métier (emprunt, retour...)
    security.py      # hash mot de passe, JWT
  alembic/
  tests/
  ```

## Phase 1 : Base de données
- [ ] `database.py` : engine SQLAlchemy (`oracle+oracledb://...`) et dépendance `get_db()` construite avec `yield`
- [ ] Modèles SQLAlchemy :
  - [ ] **Utilisateur** : id, nom, email (unique), téléphone, mot_de_passe_hash, date_inscription, rôle (admin/membre)
  - [ ] **Livre** : id, titre, auteur, genre, date_publication, disponible (booléen), éventuellement ISBN
  - [ ] **Emprunt** : id, user_id (FK), livre_id (FK), date_emprunt, date_retour_prévue, date_retour (null tant que le livre n'est pas rendu)
  - [ ] Relations `relationship()`, contraintes et index (email unique, index sur titre/auteur)
- [ ] `alembic init alembic` et configurer `env.py` avec les modèles (`target_metadata`)
- [ ] Première migration : `alembic revision --autogenerate -m "init"` puis `alembic upgrade head`
- [ ] Une **deuxième migration** qui modifie le schéma (ex. ajout de `genre` ou `date_retour_prevue`) pour montrer l'évolution avec Alembic à la soutenance

## Phase 2 : Utilisateurs et authentification
- [ ] Schémas Pydantic : `UserCreate` (`EmailStr`, validation du téléphone), `UserOut` (sans mot de passe)
- [ ] `POST /users/register` : inscription avec mot de passe hashé
- [ ] `POST /auth/token` : connexion avec **OAuth2PasswordRequestForm**, renvoie un **JWT**
  📖 *Doc : Tutorial → Security → « OAuth2 with Password (and hashing), Bearer with JWT tokens »*
- [ ] Dépendance `get_current_user` avec `Depends(oauth2_scheme)` 📖 *Doc : Dependencies*
- [ ] Dépendance `get_current_admin` pour les routes réservées aux admins
- [ ] `GET /users/me` : profil de l'utilisateur connecté
- [ ] `GET /users/me/loans` : emprunts en cours
- [ ] `GET /users/me/history` : historique des emprunts

## Phase 3 : Livres
- [ ] Schémas `BookCreate`, `BookUpdate` (champs optionnels), `BookOut`
- [ ] `POST /books` : ajout (admin)
- [ ] `PATCH /books/{id}` : modification (admin) 📖 *Doc : Body – Updates (`model_dump(exclude_unset=True)`)*
- [ ] `DELETE /books/{id}` : suppression (admin), refusée si le livre est emprunté
- [ ] `GET /books/{id}` : détail, `HTTPException(404)` si introuvable
- [ ] `GET /books?title=&author=&genre=&skip=&limit=` : recherche et pagination
  📖 *Doc : Query Parameters and String Validations (`Query(min_length=...)`)*

## Phase 4 : Emprunts
- [ ] `POST /loans` (body : `book_id`) : vérifier la disponibilité, créer l'emprunt et passer `disponible` à False, **dans une seule transaction**
- [ ] `POST /loans/{id}/return` : renseigner `date_retour`, remettre `disponible` à True, vérifier que c'est bien l'emprunteur
- [ ] Codes d'erreur adaptés : 409 (livre déjà emprunté), 403 (pas le droit), 404 (introuvable)
- [ ] (Bonus) Limite d'emprunts simultanés par utilisateur, liste des retards pour les admins

## Phase 5 : Fonctions FastAPI avancées (demandées par le prof)
- [ ] **APIRouter** avec `prefix` et `tags` 📖 *Bigger Applications – Multiple Files*
- [ ] **response_model** et **status_code** sur chaque route (201 création, 204 suppression) 📖 *Response Model*
- [ ] **Lifespan events** : vérifier la connexion à la base au démarrage 📖 *Advanced → Lifespan Events*
- [ ] **Middleware CORS** 📖 *CORS*
- [ ] **Métadonnées Swagger** : titre, description, tags décrits, exemples dans les schémas (`json_schema_extra`)
  📖 *Metadata and Docs URLs, Declare Request Example Data*
- [ ] **Gestionnaires d'exceptions** personnalisés 📖 *Handling Errors*
- [ ] (Bonus) **BackgroundTasks** : journaliser ou « envoyer » un mail de confirmation d'emprunt 📖 *Background Tasks*

## Phase 6 : Tests et qualité
- [ ] Tests avec **TestClient** et pytest 📖 *Testing*
- [ ] Remplacer `get_db` par une base de test via `app.dependency_overrides` 📖 *Testing Dependencies with Overrides*
- [ ] Tester au minimum : inscription, connexion, emprunt d'un livre indisponible (doit échouer), retour
- [ ] Script de seed (quelques livres et utilisateurs pour la démo)

## Phase 7 : Livrables et soutenance
- [ ] Vérifier que `/docs` (Swagger) est complet et propre
- [ ] README : installation, copie de `.env.example` vers `.env`, `docker compose up -d`, `alembic upgrade head`, `fastapi dev`
- [ ] Schéma de la base (MCD ou diagramme des 3 tables)
- [ ] Préparer les **justifications des choix techniques** : JWT vs sessions, hash Argon2, utilisateur Oracle aux droits limités, transaction sur l'emprunt, séparation routers/services/schémas
- [ ] Scénario de démo : inscription → connexion → recherche → emprunt → double emprunt (erreur) → retour → historique
- [ ] Répartir le travail dans le binôme (ex. base/Alembic/modèles d'un côté, authentification/routes de l'autre)

---

**Conseil :** pour les phases 2 et 5, suivre le tutoriel officiel dans l'ordre : https://fastapi.tiangolo.com → *Learn → Tutorial – User Guide → Security*, puis *Bigger Applications*.
