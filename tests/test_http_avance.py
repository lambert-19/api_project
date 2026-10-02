"""ETag (304 / 412), pagination dans les en-têtes, export CSV en flux."""

import csv
import io
import re
from datetime import date, timedelta

from models import Emprunt

# --- ETag / 304 Not Modified --------------------------------------------------


def test_detail_livre_avec_etag(client, creer_livre):
    reponse = client.get(f"/books/{creer_livre().id}")

    assert re.fullmatch(r'"[0-9a-f]{20}"', reponse.headers["etag"])
    assert reponse.headers["cache-control"] == "no-cache"


def test_304_si_le_livre_n_a_pas_change(client, creer_livre):
    url = f"/books/{creer_livre().id}"
    etag = client.get(url).headers["etag"]

    for entete in (etag, f"W/{etag}", f'"autre", {etag}', "*"):
        reponse = client.get(url, headers={"If-None-Match": entete})
        assert reponse.status_code == 304
        assert reponse.content == b""
        assert reponse.headers["etag"] == etag


def test_200_si_le_livre_a_change(client, admin, creer_livre):
    _, entetes = admin
    url = f"/books/{creer_livre().id}"
    ancien = client.get(url).headers["etag"]
    client.patch(url, json={"genre": "Roman"}, headers=entetes)

    reponse = client.get(url, headers={"If-None-Match": ancien})

    assert reponse.status_code == 200
    assert reponse.json()["genre"] == "Roman"
    assert reponse.headers["etag"] != ancien


# --- If-Match / 412 Precondition Failed ---------------------------------------


def test_modification_avec_if_match_a_jour(client, admin, creer_livre):
    _, entetes = admin
    url = f"/books/{creer_livre().id}"
    etag = client.get(url).headers["etag"]

    reponse = client.patch(url, json={"genre": "Roman"}, headers={**entetes, "If-Match": etag})

    assert reponse.status_code == 200
    assert reponse.headers["etag"] == client.get(url).headers["etag"] != etag


def test_412_si_un_autre_admin_a_modifie_entre_temps(client, admin, creer_livre):
    _, entetes = admin
    url = f"/books/{creer_livre().id}"
    etag_lu_par_alice = client.get(url).headers["etag"]
    client.patch(url, json={"genre": "Policier"}, headers=entetes)  # Bob modifie d'abord

    reponse = client.patch(url, json={"genre": "Roman"}, headers={**entetes, "If-Match": etag_lu_par_alice})

    assert reponse.status_code == 412
    assert client.get(url).json()["genre"] == "Policier"  # la modification de Bob n'est pas écrasée


def test_if_match_refuse_un_etag_faible(client, admin, creer_livre):
    _, entetes = admin
    url = f"/books/{creer_livre().id}"
    etag = client.get(url).headers["etag"]

    assert client.patch(url, json={"genre": "Roman"}, headers={**entetes, "If-Match": f"W/{etag}"}).status_code == 412


# --- Pagination : X-Total-Count et Link ---------------------------------------


def _liens(reponse) -> dict[str, str]:
    """{"next": "skip=4&limit=2", ...} à partir de l'en-tête Link."""
    return {
        rel: re.search(r"skip=\d+&limit=\d+", url).group()
        for url, rel in re.findall(r'<([^>]+)>; rel="(\w+)"', reponse.headers["link"])
    }


def test_pagination_dans_les_en_tetes(client, creer_livre):
    for i in range(5):
        creer_livre(titre=f"Paginé {i}")

    premiere = client.get("/books", params={"title": "Paginé", "limit": 2})
    milieu = client.get("/books", params={"title": "Paginé", "skip": 2, "limit": 2})
    derniere = client.get("/books", params={"title": "Paginé", "skip": 4, "limit": 2})

    assert premiere.headers["x-total-count"] == "5"
    assert _liens(premiere) == {"first": "skip=0&limit=2", "last": "skip=4&limit=2", "next": "skip=2&limit=2"}
    assert _liens(milieu) == {
        "first": "skip=0&limit=2", "last": "skip=4&limit=2", "prev": "skip=0&limit=2", "next": "skip=4&limit=2",
    }
    assert _liens(derniere) == {"first": "skip=0&limit=2", "last": "skip=4&limit=2", "prev": "skip=2&limit=2"}
    assert [livre["titre"] for livre in derniere.json()] == ["Paginé 4"]


def test_liens_conservent_les_filtres(client, creer_livre):
    creer_livre(titre="Filtre conservé")

    lien = client.get("/books", params={"title": "Filtre conservé", "limit": 1}).headers["link"]

    assert "title=Filtre" in lien


def test_aucun_resultat(client):
    reponse = client.get("/books", params={"title": "aucun-livre-ne-porte-ce-titre"})

    assert reponse.headers["x-total-count"] == "0"
    assert _liens(reponse) == {"first": "skip=0&limit=20", "last": "skip=0&limit=20"}


# --- Export CSV en flux --------------------------------------------------------


def test_export_csv_des_emprunts(client, db, membre, admin, creer_livre):
    utilisateur, entetes_membre = membre
    _, entetes_admin = admin
    en_cours = client.post("/loans", json={"livre_id": creer_livre(titre="Export en cours").id}, headers=entetes_membre)
    en_retard = client.post("/loans", json={"livre_id": creer_livre(titre="Export retard").id}, headers=entetes_membre)
    db.get(Emprunt, en_retard.json()["id"]).date_retour_prevue = date.today() - timedelta(days=2)
    db.commit()

    reponse = client.get("/loans/export", headers=entetes_admin)

    assert reponse.status_code == 200
    assert reponse.headers["content-type"] == "text/csv; charset=utf-8"
    assert reponse.headers["content-disposition"] == f'attachment; filename="emprunts_{date.today()}.csv"'
    lignes = list(csv.DictReader(io.StringIO(reponse.content.decode("utf-8-sig")), delimiter=";"))
    par_id = {int(ligne["id"]): ligne for ligne in lignes}
    assert par_id[en_cours.json()["id"]]["statut"] == "en cours"
    assert par_id[en_cours.json()["id"]]["email"] == utilisateur.email
    assert par_id[en_retard.json()["id"]]["statut"] == "en retard"


def test_export_reserve_aux_gestionnaires(client, membre):
    _, entetes = membre

    assert client.get("/loans/export", headers=entetes).status_code == 403
