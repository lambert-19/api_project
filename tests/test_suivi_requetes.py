"""Middleware de suivi : en-têtes X-Request-ID et X-Process-Time."""

import re

from config import get_settings


def test_chaque_reponse_a_un_identifiant_et_une_duree(client):
    reponse = client.get("/health")

    assert re.fullmatch(r"[0-9a-f]{32}", reponse.headers["x-request-id"])
    assert float(reponse.headers["x-process-time"]) >= 0


def test_identifiants_differents_a_chaque_requete(client):
    assert client.get("/health").headers["x-request-id"] != client.get("/health").headers["x-request-id"]


def test_identifiant_du_client_conserve(client):
    reponse = client.get("/health", headers={"X-Request-ID": "front-1234.abc"})

    assert reponse.headers["x-request-id"] == "front-1234.abc"


def test_identifiant_du_client_invalide_remplace(client):
    for invalide in ("avec espaces", "x" * 65, "<script>"):
        reponse = client.get("/health", headers={"X-Request-ID": invalide})
        assert re.fullmatch(r"[0-9a-f]{32}", reponse.headers["x-request-id"])


def test_present_aussi_sur_les_erreurs(client):
    assert "x-request-id" in client.get("/route-inexistante").headers
    trop_gros = client.post(
        "/users/register",
        content=b"x" * (get_settings().taille_max_requete + 1),
        headers={"Content-Type": "application/json"},
    )
    assert trop_gros.status_code == 413
    assert "x-request-id" in trop_gros.headers


def test_en_tetes_lisibles_par_un_site_autorise(client):
    reponse = client.get("/books", headers={"Origin": "http://localhost:3000"})

    exposes = reponse.headers["access-control-expose-headers"].lower()
    for en_tete in ("x-request-id", "x-process-time", "location", "etag", "x-total-count", "link"):
        assert en_tete in exposes
