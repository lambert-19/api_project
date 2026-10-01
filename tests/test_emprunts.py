from datetime import date, timedelta

from models import Emprunt
from services.emprunts import DUREE_EMPRUNT_JOURS, MAX_EMPRUNTS_EN_COURS


def emprunter(client, entetes, livre):
    return client.post("/loans", json={"livre_id": livre.id}, headers=entetes)


def test_emprunt(client, membre, creer_livre):
    _, entetes = membre
    livre = creer_livre()
    reponse = emprunter(client, entetes, livre)

    assert reponse.status_code == 201
    assert reponse.json()["date_retour"] is None
    assert reponse.json()["date_retour_prevue"] == str(date.today() + timedelta(days=DUREE_EMPRUNT_JOURS))
    assert client.get(f"/books/{livre.id}").json()["disponible"] is False


def test_emprunt_livre_indisponible(client, creer_utilisateur, creer_livre):
    _, alice = creer_utilisateur()
    _, bob = creer_utilisateur()
    livre = creer_livre()
    emprunter(client, alice, livre)

    reponse = emprunter(client, bob, livre)

    assert reponse.status_code == 409
    assert client.get("/users/me/loans", headers=bob).json() == []


def test_emprunt_sans_jeton_ou_livre_inexistant(client, membre, creer_livre):
    _, entetes = membre

    assert client.post("/loans", json={"livre_id": creer_livre().id}).status_code == 401
    assert client.post("/loans", json={"livre_id": 0}, headers=entetes).status_code == 404


def test_limite_emprunts_en_cours(client, membre, creer_livre):
    _, entetes = membre
    for _ in range(MAX_EMPRUNTS_EN_COURS):
        assert emprunter(client, entetes, creer_livre()).status_code == 201

    assert emprunter(client, entetes, creer_livre()).status_code == 409


def test_retour(client, membre, creer_livre):
    _, entetes = membre
    livre = creer_livre()
    emprunt_id = emprunter(client, entetes, livre).json()["id"]

    reponse = client.post(f"/loans/{emprunt_id}/return", headers=entetes)

    assert reponse.status_code == 200
    assert reponse.json()["date_retour"] is not None
    assert client.get(f"/books/{livre.id}").json()["disponible"] is True
    assert client.post(f"/loans/{emprunt_id}/return", headers=entetes).status_code == 409


def test_retour_par_un_autre_membre_refuse(client, creer_utilisateur, creer_livre):
    _, alice = creer_utilisateur()
    _, bob = creer_utilisateur()
    emprunt_id = emprunter(client, alice, creer_livre()).json()["id"]

    assert client.post(f"/loans/{emprunt_id}/return", headers=bob).status_code == 403


def test_retour_par_un_admin(client, membre, admin, creer_livre):
    _, entetes_membre = membre
    _, entetes_admin = admin
    emprunt_id = emprunter(client, entetes_membre, creer_livre()).json()["id"]

    assert client.post(f"/loans/{emprunt_id}/return", headers=entetes_admin).status_code == 200


def test_livre_rendu_peut_etre_reemprunte(client, creer_utilisateur, creer_livre):
    _, alice = creer_utilisateur()
    _, bob = creer_utilisateur()
    livre = creer_livre()
    emprunt_id = emprunter(client, alice, livre).json()["id"]
    client.post(f"/loans/{emprunt_id}/return", headers=alice)

    assert emprunter(client, bob, livre).status_code == 201


def test_emprunts_en_cours_et_historique(client, membre, creer_livre):
    _, entetes = membre
    rendu = emprunter(client, entetes, creer_livre(titre="Rendu")).json()["id"]
    client.post(f"/loans/{rendu}/return", headers=entetes)
    emprunter(client, entetes, creer_livre(titre="En cours"))

    en_cours = client.get("/users/me/loans", headers=entetes).json()
    historique = client.get("/users/me/history", headers=entetes).json()

    assert [e["livre"]["titre"] for e in en_cours] == ["En cours"]
    assert {e["livre"]["titre"] for e in historique} == {"Rendu", "En cours"}


def test_retards_reserves_aux_admins(client, db, membre, admin, creer_livre):
    utilisateur, entetes_membre = membre
    _, entetes_admin = admin
    emprunt_id = emprunter(client, entetes_membre, creer_livre(titre="En retard")).json()["id"]
    db.get(Emprunt, emprunt_id).date_retour_prevue = date.today() - timedelta(days=3)
    db.commit()

    assert client.get("/loans/overdue", headers=entetes_membre).status_code == 403
    retards = client.get("/loans/overdue", headers=entetes_admin).json()
    assert {(e["livre"]["titre"], e["utilisateur"]["email"]) for e in retards} >= {("En retard", utilisateur.email)}
