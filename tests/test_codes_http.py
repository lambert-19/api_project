"""Codes HTTP : messages en français (401, 404, 405, 422), 400 métier, en-tête Location, 413."""

from config import get_settings

TAILLE_MAX = get_settings().taille_max_requete

DUNE = {"titre": "Dune", "auteur": "Frank Herbert"}


def test_route_inexistante_404_en_francais(client):
    reponse = client.get("/route-qui-n-existe-pas")

    assert reponse.status_code == 404
    assert reponse.json() == {"detail": "Route introuvable : vérifier l'URL"}


def test_404_metier_garde_son_message(client):
    assert client.get("/books/999999999").json() == {"detail": "Livre introuvable"}


def test_mauvaise_methode_405_en_francais(client):
    reponse = client.put("/books")

    assert reponse.status_code == 405
    assert reponse.json()["detail"].startswith("Méthode PUT non autorisée sur cette route")
    assert "GET" in reponse.headers["allow"]


def test_sans_jeton_401_en_francais(client):
    reponse = client.get("/users/me")

    assert reponse.status_code == 401
    assert reponse.json()["detail"].startswith("Authentification requise")
    assert reponse.headers["www-authenticate"] == "Bearer"


def test_422_message_lisible_par_champ(client):
    reponse = client.get("/books", params={"limit": 500})

    assert reponse.status_code == 422
    assert reponse.json() == {
        "detail": "Données invalides",
        "erreurs": [
            {"emplacement": "query", "champ": "limit", "message": "Doit être inférieur ou égal à 100"}
        ],
    }


def test_422_parametre_de_recherche_inconnu(client):
    """Modèle de paramètres avec extra="forbid" : une faute de frappe n'est pas ignorée."""
    reponse = client.get("/books", params={"titel": "dune"})

    assert reponse.status_code == 422
    assert reponse.json()["erreurs"] == [{"emplacement": "query", "champ": "titel", "message": "Paramètre inconnu"}]


def test_422_champs_obligatoires(client):
    reponse = client.post("/users/register", json={})

    erreurs = {e["champ"]: e["message"] for e in reponse.json()["erreurs"]}
    assert erreurs == {"nom": "Champ obligatoire", "email": "Champ obligatoire", "mot_de_passe": "Champ obligatoire"}


def test_422_validateur_metier_sans_champ(client, admin, creer_livre):
    _, entetes = admin
    livre = creer_livre()

    reponse = client.patch(f"/books/{livre.id}", json={"titre": None}, headers=entetes)

    assert reponse.status_code == 422
    assert reponse.json()["erreurs"] == [
        {"emplacement": "body", "champ": None, "message": "titre ne peut pas être null"}
    ]


def test_patch_sans_modification_400(client, admin, creer_livre):
    _, entetes = admin
    livre = creer_livre()

    reponse = client.patch(f"/books/{livre.id}", json={}, headers=entetes)

    assert reponse.status_code == 400
    assert reponse.json() == {"detail": "Aucun champ à modifier"}


def test_creation_livre_201_avec_location(client, admin):
    _, entetes = admin

    reponse = client.post("/books", json=DUNE, headers=entetes)

    assert reponse.status_code == 201
    assert reponse.headers["location"] == f"/books/{reponse.json()['id']}"
    assert client.get(reponse.headers["location"]).json()["titre"] == "Dune"


def test_inscription_201_avec_location(client):
    reponse = client.post(
        "/users/register",
        json={"nom": "Ada", "email": "ada@test.example", "mot_de_passe": "lovelace1815"},
    )

    assert reponse.status_code == 201
    assert reponse.headers["location"] == "/users/me"


def test_corps_trop_gros_413_avec_content_length(client):
    reponse = client.post(
        "/users/register",
        content=b"x" * (TAILLE_MAX + 1),
        headers={"Content-Type": "application/json"},
    )

    assert reponse.status_code == 413
    assert reponse.json()["detail"].startswith("Corps de la requête trop volumineux")


def test_corps_trop_gros_413_sans_content_length(client):
    """Envoi « chunked » : pas de Content-Length, les octets sont comptés pendant la lecture."""
    morceaux = iter([b"x" * TAILLE_MAX, b"x"])

    reponse = client.post("/users/register", content=morceaux, headers={"Content-Type": "application/json"})

    assert reponse.status_code == 413


def test_corps_juste_sous_la_limite_accepte(client):
    """Juste sous la limite : la requête passe le middleware (puis échoue en 422, JSON invalide)."""
    reponse = client.post(
        "/users/register",
        content=b"x" * TAILLE_MAX,
        headers={"Content-Type": "application/json"},
    )

    assert reponse.status_code == 422
