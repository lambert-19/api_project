from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DatabaseError

from config import get_settings
from conftest import MOT_DE_PASSE
from database import engine
from models import Livre, Utilisateur

INJECTIONS = ["' OR '1'='1", "'; DROP TABLE livre; --", "%' UNION SELECT mot_de_passe_hash FROM utilisateur --"]


def _jeton(payload: dict, cle: str | None, algorithme: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jwt.encode(payload, cle, algorithm=algorithme)}"}


# --- Force brute -------------------------------------------------------------


def test_connexion_bloquee_apres_5_echecs(client, membre):
    utilisateur, _ = membre
    for _ in range(5):
        reponse = client.post("/auth/token", data={"username": utilisateur.email, "password": "faux"})
        assert reponse.status_code == 401

    bloquee = client.post("/auth/token", data={"username": utilisateur.email, "password": MOT_DE_PASSE})

    assert bloquee.status_code == 429
    assert int(bloquee.headers["Retry-After"]) > 0


def test_connexions_reussies_jamais_bloquees(client, membre):
    utilisateur, _ = membre
    for _ in range(10):
        reponse = client.post("/auth/token", data={"username": utilisateur.email, "password": MOT_DE_PASSE})
        assert reponse.status_code == 200


# --- Injection SQL -----------------------------------------------------------


@pytest.mark.parametrize("injection", INJECTIONS)
def test_injection_sql_dans_la_recherche(client, creer_livre, injection):
    creer_livre()

    for parametre in ("title", "author", "genre"):
        reponse = client.get("/books", params={parametre: injection})
        assert reponse.status_code == 200
        assert reponse.json() == []


@pytest.mark.parametrize("injection", INJECTIONS)
def test_injection_sql_a_la_connexion(client, membre, injection):
    reponse = client.post("/auth/token", data={"username": injection, "password": injection})

    assert reponse.status_code == 401


def test_injection_sql_stockee_comme_du_texte(client, db, admin):
    _, entetes = admin
    reponse = client.post("/books", json={"titre": INJECTIONS[1], "auteur": "X"}, headers=entetes)

    assert reponse.status_code == 201
    assert db.get(Livre, reponse.json()["id"]).titre == INJECTIONS[1]
    assert db.scalar(select(Livre).limit(1)) is not None


# --- Jetons JWT --------------------------------------------------------------


def test_jeton_non_signe_alg_none_refuse(client, membre):
    utilisateur, _ = membre
    entetes = _jeton({"sub": str(utilisateur.id), "exp": datetime.now(UTC) + timedelta(minutes=5)}, None, "none")

    assert client.get("/users/me", headers=entetes).status_code == 401


def test_jeton_modifie_pour_usurper_un_admin(client, membre, admin):
    _, entetes_membre = membre
    admin_utilisateur, _ = admin
    entete, _, signature = entetes_membre["Authorization"].removeprefix("Bearer ").split(".")
    faux_contenu = jwt.utils.base64url_encode(f'{{"sub":"{admin_utilisateur.id}","exp":9999999999}}'.encode()).decode()

    reponse = client.get("/users/me", headers={"Authorization": f"Bearer {entete}.{faux_contenu}.{signature}"})

    assert reponse.status_code == 401


@pytest.mark.parametrize("payload", [{"sub": "0"}, {"sub": "abc"}, {}])
def test_jeton_avec_utilisateur_invalide(client, payload):
    settings = get_settings()
    payload = {**payload, "exp": datetime.now(UTC) + timedelta(minutes=5)}
    entetes = _jeton(payload, settings.secret_key.get_secret_value(), settings.algorithm)

    assert client.get("/users/me", headers=entetes).status_code == 401


# --- Mots de passe -----------------------------------------------------------


def test_mot_de_passe_stocke_hashe_avec_argon2(client, db):
    client.post(
        "/users/register",
        json={"nom": "A", "email": "hash@test.example", "mot_de_passe": "motdepasse-clair"},
    )
    utilisateur = db.scalar(select(Utilisateur).where(Utilisateur.email == "hash@test.example"))

    assert utilisateur.mot_de_passe_hash.startswith("$argon2id$")
    assert "motdepasse-clair" not in utilisateur.mot_de_passe_hash


def test_meme_mot_de_passe_hashs_differents(client, db):
    for email in ("sel1@test.example", "sel2@test.example"):
        client.post("/users/register", json={"nom": "A", "email": email, "mot_de_passe": "identique123"})
    hashs = db.scalars(select(Utilisateur.mot_de_passe_hash).where(Utilisateur.email.like("sel%@test.example")))

    assert len(set(hashs)) == 2


# --- Droits du compte Oracle de l'API ----------------------------------------


@pytest.mark.parametrize(
    ("sql", "code_oracle"),
    [
        ("CREATE TABLE pirate (x INT)", "ORA-01031"),
        ("DROP TABLE livre", "ORA-01031"),
        ("ALTER TABLE livre ADD pirate INT", "ORA-01031"),
        ("TRUNCATE TABLE emprunt", "ORA-01031"),
        ("GRANT SELECT ON utilisateur TO PUBLIC", "ORA-01031"),
        ("SELECT username FROM dba_users", "ORA-00942"),
    ],
)
def test_compte_api_ne_peut_pas_modifier_la_structure(sql, code_oracle):
    with engine.connect() as connexion:
        with pytest.raises(DatabaseError, match=code_oracle):
            connexion.execute(text(sql))
