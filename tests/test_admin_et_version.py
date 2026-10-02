"""Routeur /admin protégé au niveau du routeur, et versionnement /v1."""

import pytest

from main import app

# Toutes les routes /v1/admin, lues dans le schéma OpenAPI (liste complète des routes de l'app)
ROUTES_ADMIN = [
    (methode.upper(), chemin.replace("{livre_id}", "1"))
    for chemin, operations in app.openapi()["paths"].items()
    if chemin.startswith("/v1/admin/")
    for methode in operations
]


def test_le_routeur_admin_contient_les_routes_de_gestion():
    assert set(ROUTES_ADMIN) == {
        ("POST", "/v1/admin/books"),
        ("PATCH", "/v1/admin/books/1"),
        ("DELETE", "/v1/admin/books/1"),
        ("PUT", "/v1/admin/books/1/cover"),
        ("DELETE", "/v1/admin/books/1/cover"),
        ("GET", "/v1/admin/loans/overdue"),
        ("GET", "/v1/admin/loans/export"),
    }


@pytest.mark.parametrize(("methode", "chemin"), ROUTES_ADMIN)
def test_toute_route_admin_refuse_un_membre(client, membre, methode, chemin):
    """Vérifié pour CHAQUE route du routeur : une route ajoutée plus tard est couverte automatiquement."""
    _, entetes = membre

    reponse = client.request(methode, chemin, json={}, headers=entetes)

    assert reponse.status_code == 403
    assert reponse.json() == {"detail": "Réservé aux administrateurs"}


@pytest.mark.parametrize(("methode", "chemin"), ROUTES_ADMIN)
def test_toute_route_admin_exige_d_etre_connecte(client, methode, chemin):
    assert client.request(methode, chemin, json={}).status_code == 401


def test_role_admin_et_permission_sont_verifies(client, admin):
    """Niveau 1 (routeur /admin) : rôle admin. Niveau 2 (sous-routeur) : permission du jeton."""
    utilisateur, _ = admin
    jeton = client.post(
        "/v1/auth/token",
        data={"username": utilisateur.email, "password": "motdepasse-test", "scope": "livres:ecrire"},
    ).json()["access_token"]
    entetes = {"Authorization": f"Bearer {jeton}"}

    assert client.post("/v1/admin/books", json={"titre": "T", "auteur": "A"}, headers=entetes).status_code == 201
    reponse = client.get("/v1/admin/loans/overdue", headers=entetes)
    assert reponse.status_code == 403
    assert reponse.json() == {"detail": "Permission insuffisante : emprunts:gerer requis"}


# --- Versionnement ----------------------------------------------------------------


def test_toutes_les_routes_de_l_api_sont_versionnees():
    hors_version = {"/health"}
    chemins = app.openapi()["paths"]

    assert all(chemin.startswith("/v1/") or chemin in hors_version for chemin in chemins)


@pytest.mark.parametrize("chemin", ["/books", "/auth/token", "/users/me", "/loans"])
def test_anciennes_url_sans_version_introuvables(client, chemin):
    assert client.get(chemin).status_code == 404


def test_swagger_se_connecte_sur_l_url_versionnee():
    flux = app.openapi()["components"]["securitySchemes"]["OAuth2PasswordBearer"]["flows"]["password"]

    assert flux["tokenUrl"] == "/v1/auth/token"


def test_liens_de_pagination_versionnes(client):
    assert "/v1/books?" in client.get("/v1/books").headers["link"]
