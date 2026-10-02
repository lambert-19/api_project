"""Couvertures de livres : envoi (UploadFile), vérification du format, lecture, suppression."""

import pytest

from models import Couverture
from services.couvertures import TAILLE_MAX_COUVERTURE

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200
WEBP = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 200


def envoyer(client, entetes, livre_id, contenu, nom="couverture.png", type_annonce="image/png"):
    return client.put(
        f"/v1/admin/books/{livre_id}/cover",
        files={"fichier": (nom, contenu, type_annonce)},
        headers=entetes,
    )


@pytest.mark.parametrize(("contenu", "type_mime"), [(PNG, "image/png"), (JPEG, "image/jpeg"), (WEBP, "image/webp")])
def test_envoi_et_lecture_de_la_couverture(client, admin, creer_livre, contenu, type_mime):
    _, entetes = admin
    livre = creer_livre()

    reponse = envoyer(client, entetes, livre.id, contenu)
    image = client.get(f"/v1/books/{livre.id}/cover")

    assert reponse.status_code == 200
    assert reponse.json()["couverture_url"] == f"/v1/books/{livre.id}/cover"
    assert image.status_code == 200
    assert image.content == contenu
    assert image.headers["content-type"] == type_mime  # d'après le contenu, pas le type annoncé
    assert image.headers["x-content-type-options"] == "nosniff"


def test_couverture_url_dans_le_detail_et_la_recherche(client, admin, creer_livre):
    _, entetes = admin
    avec = creer_livre(titre="Couv avec")
    sans = creer_livre(titre="Couv sans")
    envoyer(client, entetes, avec.id, PNG)

    assert client.get(f"/v1/books/{avec.id}").json()["couverture_url"] == f"/v1/books/{avec.id}/cover"
    assert client.get(f"/v1/books/{sans.id}").json()["couverture_url"] is None
    resultats = {l["titre"]: l["couverture_url"] for l in client.get("/v1/books", params={"title": "Couv "}).json()}
    assert resultats == {"Couv avec": f"/v1/books/{avec.id}/cover", "Couv sans": None}
    assert "nb_couvertures" not in client.get(f"/v1/books/{avec.id}").json()  # champ interne non exposé


def test_remplacement_de_la_couverture(client, admin, creer_livre):
    _, entetes = admin
    livre = creer_livre()
    envoyer(client, entetes, livre.id, PNG)

    envoyer(client, entetes, livre.id, JPEG, nom="nouvelle.jpg", type_annonce="image/jpeg")

    image = client.get(f"/v1/books/{livre.id}/cover")
    assert image.content == JPEG and image.headers["content-type"] == "image/jpeg"


def test_304_si_l_image_n_a_pas_change(client, admin, creer_livre):
    _, entetes = admin
    livre = creer_livre()
    envoyer(client, entetes, livre.id, PNG)
    etag = client.get(f"/v1/books/{livre.id}/cover").headers["etag"]

    reponse = client.get(f"/v1/books/{livre.id}/cover", headers={"If-None-Match": etag})

    assert reponse.status_code == 304
    assert reponse.content == b""


@pytest.mark.parametrize(
    ("contenu", "nom", "type_annonce"),
    [
        (b"pas une image", "photo.jpg", "image/jpeg"),  # fichier texte renommé en .jpg
        (b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', "c.svg", "image/svg+xml"),
        (b"%PDF-1.7 ...", "c.pdf", "application/pdf"),
    ],
)
def test_format_non_supporte_415(client, admin, creer_livre, contenu, nom, type_annonce):
    _, entetes = admin

    reponse = envoyer(client, entetes, creer_livre().id, contenu, nom, type_annonce)

    assert reponse.status_code == 415
    assert reponse.json() == {"detail": "Format non supporté : image JPEG, PNG ou WebP attendue"}


def test_image_trop_volumineuse_413(client, admin, creer_livre):
    _, entetes = admin
    trop_gros = b"\x89PNG\r\n\x1a\n" + b"\x00" * TAILLE_MAX_COUVERTURE

    reponse = envoyer(client, entetes, creer_livre().id, trop_gros)

    assert reponse.status_code == 413
    assert reponse.json()["detail"].startswith("Image trop volumineuse")


def test_fichier_vide_400(client, admin, creer_livre):
    _, entetes = admin

    assert envoyer(client, entetes, creer_livre().id, b"").status_code == 400


def test_sans_fichier_422(client, admin, creer_livre):
    _, entetes = admin

    reponse = client.put(f"/v1/admin/books/{creer_livre().id}/cover", headers=entetes)

    assert reponse.status_code == 422
    assert reponse.json()["erreurs"][0]["champ"] == "fichier"


def test_livre_inexistant_404(client, admin):
    _, entetes = admin

    assert envoyer(client, entetes, 999999999, PNG).status_code == 404
    assert client.get("/v1/books/999999999/cover").json() == {"detail": "Livre introuvable"}


def test_suppression_de_la_couverture(client, admin, creer_livre):
    _, entetes = admin
    livre = creer_livre()
    envoyer(client, entetes, livre.id, PNG)

    assert client.delete(f"/v1/admin/books/{livre.id}/cover", headers=entetes).status_code == 204
    assert client.get(f"/v1/books/{livre.id}/cover").json() == {"detail": "Ce livre n'a pas de couverture"}
    assert client.get(f"/v1/books/{livre.id}").json()["couverture_url"] is None
    assert client.delete(f"/v1/admin/books/{livre.id}/cover", headers=entetes).status_code == 404


def test_supprimer_le_livre_supprime_sa_couverture(client, db, admin, creer_livre):
    """ON DELETE CASCADE : la couverture disparaît avec le livre."""
    _, entetes = admin
    livre = creer_livre()
    envoyer(client, entetes, livre.id, PNG)

    assert client.delete(f"/v1/admin/books/{livre.id}", headers=entetes).status_code == 204
    db.expire_all()
    assert db.get(Couverture, livre.id) is None


def test_envoi_reserve_aux_administrateurs(client, membre, creer_livre):
    _, entetes = membre

    assert envoyer(client, entetes, creer_livre().id, PNG).status_code == 403
