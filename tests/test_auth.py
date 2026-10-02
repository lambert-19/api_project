from datetime import UTC, datetime, timedelta

import jwt

from config import get_settings
from conftest import MOT_DE_PASSE

INSCRIPTION = {
    "nom": "Marie Curie",
    "email": "Marie.Curie@Test.example",
    "telephone": "+33 6 12 34 56 78",
    "mot_de_passe": "radium1898",
}


def test_inscription(client):
    reponse = client.post("/users/register", json=INSCRIPTION)

    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["email"] == "marie.curie@test.example"
    assert corps["role"] == "membre"
    assert "mot_de_passe" not in corps and "mot_de_passe_hash" not in corps


def test_inscription_email_deja_utilise(client):
    client.post("/users/register", json=INSCRIPTION)
    reponse = client.post("/users/register", json={**INSCRIPTION, "email": "MARIE.curie@test.example"})

    assert reponse.status_code == 409


def test_inscription_donnees_invalides(client):
    reponse = client.post(
        "/users/register",
        json={"nom": "", "email": "pas-un-email", "telephone": "abc", "mot_de_passe": "court"},
    )

    assert reponse.status_code == 422
    champs_en_erreur = {erreur["champ"] for erreur in reponse.json()["erreurs"]}
    assert champs_en_erreur == {"nom", "email", "telephone", "mot_de_passe"}


def test_inscription_ne_permet_pas_de_devenir_admin(client):
    reponse = client.post("/users/register", json={**INSCRIPTION, "role": "admin"})

    assert reponse.json()["role"] == "membre"


def test_connexion(client, membre):
    utilisateur, _ = membre
    reponse = client.post("/auth/token", data={"username": utilisateur.email.upper(), "password": MOT_DE_PASSE})

    assert reponse.status_code == 200
    assert reponse.json()["token_type"] == "bearer"


def test_connexion_mauvais_mot_de_passe_ou_email_inconnu(client, membre):
    utilisateur, _ = membre
    mauvais_mdp = client.post("/auth/token", data={"username": utilisateur.email, "password": "faux"})
    inconnu = client.post("/auth/token", data={"username": "inconnu@test.example", "password": "faux"})

    assert mauvais_mdp.status_code == inconnu.status_code == 401
    assert mauvais_mdp.json() == inconnu.json()


def test_profil(client, membre):
    utilisateur, entetes = membre
    reponse = client.get("/users/me", headers=entetes)

    assert reponse.status_code == 200
    assert reponse.json()["email"] == utilisateur.email


def test_profil_sans_jeton_ou_jeton_falsifie(client):
    assert client.get("/users/me").status_code == 401
    assert client.get("/users/me", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401


def test_jeton_expire(client, membre):
    utilisateur, _ = membre
    settings = get_settings()
    jeton = jwt.encode(
        {"sub": str(utilisateur.id), "exp": datetime.now(UTC) - timedelta(minutes=1)},
        settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm,
    )

    assert client.get("/users/me", headers={"Authorization": f"Bearer {jeton}"}).status_code == 401


def test_jeton_signe_avec_une_autre_cle(client, membre):
    utilisateur, _ = membre
    jeton = jwt.encode({"sub": str(utilisateur.id), "exp": datetime.now(UTC) + timedelta(minutes=5)}, "x" * 32)

    assert client.get("/users/me", headers={"Authorization": f"Bearer {jeton}"}).status_code == 401
