"""Fixtures communes.

Les tests utilisent la vraie base Oracle (docker compose up -d), avec le compte de l'API.
Chaque test s'exécute dans une transaction annulée à la fin : la base n'est jamais modifiée.
"""

from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from database import engine, get_db
from main import app
from models import Livre, RoleUtilisateur, Utilisateur
from security import hasher_mot_de_passe

MOT_DE_PASSE = "motdepasse-test"

Entetes = dict[str, str]


@pytest.fixture
def db() -> Iterator[Session]:
    with engine.connect() as connexion:
        transaction = connexion.begin()
        session = Session(
            bind=connexion,
            join_transaction_mode="create_savepoint",
            autoflush=False,
            expire_on_commit=False,
        )
        yield session
        session.close()
        transaction.rollback()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def creer_utilisateur(db: Session, client: TestClient) -> Callable[..., tuple[Utilisateur, Entetes]]:
    """Crée un utilisateur et renvoie (utilisateur, en-têtes d'authentification)."""
    compteur = 0

    def _creer(role: RoleUtilisateur = RoleUtilisateur.MEMBRE) -> tuple[Utilisateur, Entetes]:
        nonlocal compteur
        compteur += 1
        email = f"{role.value}{compteur}@test.example"
        utilisateur = Utilisateur(
            nom=f"Test {compteur}",
            email=email,
            mot_de_passe_hash=hasher_mot_de_passe(MOT_DE_PASSE),
            role=role,
        )
        db.add(utilisateur)
        db.commit()
        reponse = client.post("/auth/token", data={"username": email, "password": MOT_DE_PASSE})
        return utilisateur, {"Authorization": f"Bearer {reponse.json()['access_token']}"}

    return _creer


@pytest.fixture
def membre(creer_utilisateur) -> tuple[Utilisateur, Entetes]:
    return creer_utilisateur()


@pytest.fixture
def admin(creer_utilisateur) -> tuple[Utilisateur, Entetes]:
    return creer_utilisateur(RoleUtilisateur.ADMIN)


@pytest.fixture
def creer_livre(db: Session) -> Callable[..., Livre]:
    def _creer(**champs) -> Livre:
        livre = Livre(**{"titre": "Livre de test", "auteur": "Auteur Test", **champs})
        db.add(livre)
        db.commit()
        return livre

    return _creer
