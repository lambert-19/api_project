from datetime import date

from models import Emprunt

DUNE = {
    "titre": "Dune",
    "auteur": "Frank Herbert",
    "genre": "Science-fiction",
    "date_publication": "1965-08-01",
    "isbn": "9799999999990",
}


def test_ajout_reserve_aux_admins(client, membre):
    _, entetes = membre

    assert client.post("/books", json=DUNE).status_code == 401
    assert client.post("/books", json=DUNE, headers=entetes).status_code == 403


def test_ajout_par_admin(client, admin):
    _, entetes = admin
    reponse = client.post("/books", json=DUNE, headers=entetes)

    assert reponse.status_code == 201
    assert reponse.json()["disponible"] is True


def test_ajout_isbn_deja_utilise(client, admin):
    _, entetes = admin
    client.post("/books", json=DUNE, headers=entetes)

    assert client.post("/books", json=DUNE, headers=entetes).status_code == 409


def test_ajout_isbn_invalide(client, admin):
    _, entetes = admin

    assert client.post("/books", json={**DUNE, "isbn": "12"}, headers=entetes).status_code == 422


def test_recherche(client, creer_livre):
    creer_livre(titre="Les Misérables", auteur="Victor Hugo (test)", genre="Roman-test")
    creer_livre(titre="Notre-Dame de Paris", auteur="Victor Hugo (test)", genre="Roman-test")
    creer_livre(titre="Fondation", auteur="Isaac Asimov (test)", genre="SF-test")

    def titres(params):
        return [livre["titre"] for livre in client.get("/books", params=params).json()]

    assert titres({"author": "HUGO (TEST)"}) == ["Les Misérables", "Notre-Dame de Paris"]
    assert titres({"genre": "sf-test"}) == ["Fondation"]
    assert titres({"title": "dame de", "author": "hugo (test)"}) == ["Notre-Dame de Paris"]
    assert titres({"author": "hugo (test)", "limit": 1, "skip": 1}) == ["Notre-Dame de Paris"]


def test_recherche_limite_maximale(client):
    assert client.get("/books", params={"limit": 500}).status_code == 422


def test_detail(client, creer_livre):
    livre = creer_livre()

    assert client.get(f"/books/{livre.id}").json()["titre"] == livre.titre
    assert client.get("/books/0").status_code == 404


def test_modification_partielle(client, admin, creer_livre):
    _, entetes = admin
    livre = creer_livre(genre="Roman")
    reponse = client.patch(f"/books/{livre.id}", json={"genre": "Classique"}, headers=entetes)

    assert reponse.status_code == 200
    assert reponse.json()["genre"] == "Classique"
    assert reponse.json()["titre"] == livre.titre


def test_modification_titre_null_refusee(client, admin, creer_livre):
    _, entetes = admin
    livre = creer_livre()

    assert client.patch(f"/books/{livre.id}", json={"titre": None}, headers=entetes).status_code == 422


def test_livre_emprunte_ne_peut_pas_etre_remis_disponible(client, admin, membre, creer_livre):
    _, entetes_admin = admin
    _, entetes_membre = membre
    livre = creer_livre()
    client.post("/loans", json={"livre_id": livre.id}, headers=entetes_membre)

    reponse = client.patch(f"/books/{livre.id}", json={"disponible": True}, headers=entetes_admin)

    assert reponse.status_code == 409


def test_suppression(client, admin, creer_livre):
    _, entetes = admin
    livre = creer_livre()

    assert client.delete(f"/books/{livre.id}", headers=entetes).status_code == 204
    assert client.get(f"/books/{livre.id}").status_code == 404


def test_suppression_refusee_si_historique(client, db, admin, membre, creer_livre):
    _, entetes = admin
    utilisateur, _ = membre
    livre = creer_livre()
    db.add(Emprunt(utilisateur=utilisateur, livre=livre, date_retour_prevue=date.today()))
    db.commit()

    assert client.delete(f"/books/{livre.id}", headers=entetes).status_code == 409
