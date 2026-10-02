"""Permissions (scopes OAuth2) : attribution à la connexion et contrôle sur les routes."""

from conftest import MOT_DE_PASSE
from models import RoleUtilisateur

DUNE = {"titre": "Dune", "auteur": "Frank Herbert"}


def connexion(client, utilisateur, scope: str | None = None):
    donnees = {"username": utilisateur.email, "password": MOT_DE_PASSE}
    if scope is not None:
        donnees["scope"] = scope
    return client.post("/v1/auth/token", data=donnees)


def entetes(reponse) -> dict[str, str]:
    return {"Authorization": f"Bearer {reponse.json()['access_token']}"}


def test_scopes_par_defaut_selon_le_role(client, membre, admin):
    assert connexion(client, membre[0]).json()["scope"] == "emprunts profil"
    assert connexion(client, admin[0]).json()["scope"] == "emprunts emprunts:gerer livres:ecrire profil"


def test_jeton_lecture_seule(client, membre, creer_livre):
    reponse = connexion(client, membre[0], scope="profil")
    lecture_seule = entetes(reponse)

    assert reponse.json()["scope"] == "profil"
    assert client.get("/v1/users/me", headers=lecture_seule).status_code == 200
    emprunt = client.post("/v1/loans", json={"livre_id": creer_livre().id}, headers=lecture_seule)
    assert emprunt.status_code == 403
    assert emprunt.json() == {"detail": "Permission insuffisante : emprunts requis"}
    assert 'error="insufficient_scope"' in emprunt.headers["www-authenticate"]


def test_permission_hors_du_role_ignoree(client, membre):
    reponse = connexion(client, membre[0], scope="profil livres:ecrire")

    assert reponse.json()["scope"] == "profil"
    assert client.post("/v1/admin/books", json=DUNE, headers=entetes(reponse)).status_code == 403


def test_permission_inconnue_400(client, membre):
    reponse = connexion(client, membre[0], scope="profil livres:tout")

    assert reponse.status_code == 400
    assert reponse.json() == {"detail": "Permission inconnue : livres:tout"}


def test_admin_avec_jeton_restreint(client, admin):
    restreint = entetes(connexion(client, admin[0], scope="profil"))

    assert client.post("/v1/admin/books", json=DUNE, headers=restreint).status_code == 403
    assert client.get("/v1/admin/loans/overdue", headers=restreint).status_code == 403


def test_retour_emprunt_d_un_autre_sans_emprunts_gerer(client, membre, admin, creer_livre):
    emprunt_id = client.post("/v1/loans", json={"livre_id": creer_livre().id}, headers=membre[1]).json()["id"]
    admin_sans_gestion = entetes(connexion(client, admin[0], scope="emprunts"))

    reponse = client.post(f"/v1/loans/{emprunt_id}/return", headers=admin_sans_gestion)

    assert reponse.status_code == 403
    assert reponse.json() == {"detail": "Cet emprunt ne vous appartient pas"}


def test_admin_retrograde_perd_ses_droits_immediatement(client, db, admin):
    utilisateur, entetes_admin = admin
    assert client.post("/v1/admin/books", json=DUNE, headers=entetes_admin).status_code == 201

    utilisateur.role = RoleUtilisateur.MEMBRE
    db.commit()

    # Le jeton contient encore livres:ecrire, mais le rôle actuel ne l'autorise plus
    assert client.post("/v1/admin/books", json={**DUNE, "titre": "Dune 2"}, headers=entetes_admin).status_code == 403
