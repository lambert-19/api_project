from typing import Annotated

from fastapi import APIRouter, File, Header, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy import ColumnElement, exists, func, select
from sqlalchemy.exc import IntegrityError

from dependances import SessionDb, permission
from etag import correspond, etag_de, etag_octets
from models import Couverture, Emprunt, Livre
from services import couvertures
from reponses import LIVRE_INTROUVABLE, admin_requis, creation, erreur
from schemas.livre import FiltresLivres, LivreCreate, LivreOut, LivreUpdate

# Consultation publique : /v1/books
router = APIRouter(prefix="/books", tags=["Livres"])

# Gestion de l'inventaire : /v1/admin/books (inclus dans routers/admin.py).
# La permission est exigée une seule fois, pour toutes les routes de ce routeur,
# et ses codes 401 / 403 sont documentés une seule fois aussi.
router_admin = APIRouter(
    prefix="/books",
    dependencies=[permission("livres:ecrire")],
    responses=admin_requis("livres:ecrire"),
)

ISBN_EN_DOUBLE = "Un livre avec cet ISBN existe déjà"


def _en_tete(description: str, type_: str = "string") -> dict:
    return {"description": description, "schema": {"type": type_}}


def _get_livre(db: SessionDb, livre_id: int, verrouiller: bool = False) -> Livre:
    livre = db.get(Livre, livre_id, with_for_update=verrouiller)
    if livre is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Livre introuvable")
    return livre


def _conditions(filtres: FiltresLivres) -> list[ColumnElement[bool]]:
    conditions = []
    if filtres.title:
        conditions.append(func.lower(Livre.titre).contains(filtres.title.lower()))
    if filtres.author:
        conditions.append(func.lower(Livre.auteur).contains(filtres.author.lower()))
    if filtres.genre:
        conditions.append(func.lower(Livre.genre) == filtres.genre.lower())
    if filtres.available is not None:
        conditions.append(Livre.disponible == filtres.available)
    return conditions


def _liens_pagination(request: Request, skip: int, limit: int, total: int) -> str:
    """En-tête Link (RFC 8288) : URL des pages first / prev / next / last, comme l'API GitHub."""
    pages = {"first": 0, "last": max(total - 1, 0) // limit * limit}
    if skip > 0:
        pages["prev"] = max(skip - limit, 0)
    if skip + limit < total:
        pages["next"] = skip + limit
    return ", ".join(
        f'<{request.url.include_query_params(skip=page_skip, limit=limit)}>; rel="{rel}"'
        for rel, page_skip in pages.items()
    )


def _a_des_emprunts(db: SessionDb, livre_id: int, en_cours_seulement: bool) -> bool:
    condition = Emprunt.livre_id == livre_id
    if en_cours_seulement:
        condition &= Emprunt.date_retour.is_(None)
    return bool(db.scalar(select(exists().where(condition))))


def _commit_ou_conflit(db: SessionDb) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, ISBN_EN_DOUBLE)


@router.get(
    "",
    response_model=list[LivreOut],
    responses={
        200: {
            "description": "Page de résultats",
            "headers": {
                "X-Total-Count": _en_tete("Nombre total de livres correspondant à la recherche", "integer"),
                "Link": _en_tete('URL des pages voisines : rel="first", "prev", "next", "last"'),
            },
        }
    },
)
def rechercher_livres(
    db: SessionDb, filtres: Annotated[FiltresLivres, Query()], request: Request, response: Response
) -> list[Livre]:
    """Recherche par titre, auteur ou genre (insensible à la casse), avec pagination.

    Un paramètre inconnu (faute de frappe comme `titel`) est refusé en 422 au lieu d'être ignoré.
    Les en-têtes `X-Total-Count` et `Link` donnent le nombre total de résultats et l'URL des autres pages.
    """
    conditions = _conditions(filtres)
    total = db.scalar(select(func.count()).select_from(Livre).where(*conditions)) or 0
    requete = (
        select(Livre)
        .where(*conditions)
        .order_by(Livre.titre, Livre.id)
        .offset(filtres.skip)
        .limit(filtres.limit)
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["Link"] = _liens_pagination(request, filtres.skip, filtres.limit, total)
    return list(db.scalars(requete))


@router.get(
    "/{livre_id}",
    response_model=LivreOut,
    responses={
        200: {
            "description": "Le livre, avec son ETag",
            "headers": {"ETag": _en_tete("Empreinte du contenu, à renvoyer dans If-None-Match ou If-Match")},
        },
        304: {"description": "Not Modified : le livre n'a pas changé depuis l'ETag envoyé (réponse sans contenu)"},
        **LIVRE_INTROUVABLE,
    },
)
def detail_livre(
    livre_id: int,
    db: SessionDb,
    response: Response,
    if_none_match: Annotated[
        str | None, Header(description="ETag de la copie du client : 304 si le livre n'a pas changé")
    ] = None,
) -> LivreOut | Response:
    """Informations détaillées d'un livre.

    Requête conditionnelle : renvoyer l'ETag reçu dans `If-None-Match` ; si le livre n'a pas
    changé, la réponse est `304 Not Modified`, sans contenu.
    """
    livre = LivreOut.model_validate(_get_livre(db, livre_id))
    entetes = {"ETag": etag_de(livre), "Cache-Control": "no-cache"}  # no-cache : revalider à chaque fois
    if correspond(if_none_match, entetes["ETag"], comparaison_faible=True):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=entetes)
    response.headers.update(entetes)
    return livre


@router.get(
    "/{livre_id}/cover",
    response_class=Response,
    responses={
        200: {
            "description": "Image de couverture (JPEG, PNG ou WebP), avec son ETag",
            "content": {"image/jpeg": {}, "image/png": {}, "image/webp": {}},
        },
        304: {"description": "Not Modified : l'image n'a pas changé depuis l'ETag envoyé"},
        404: erreur("Livre introuvable, ou livre sans couverture", "Livre introuvable", "Ce livre n'a pas de couverture"),
    },
)
def couverture_livre(
    livre_id: int,
    db: SessionDb,
    if_none_match: Annotated[str | None, Header(description="ETag de l'image déjà téléchargée")] = None,
) -> Response:
    """Image de couverture d'un livre. Son URL est donnée par `couverture_url` dans le livre."""
    _get_livre(db, livre_id)
    couverture = db.get(Couverture, livre_id)
    if couverture is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ce livre n'a pas de couverture")
    entetes = {
        "ETag": etag_octets(couverture.contenu),
        "Cache-Control": "no-cache",
        # Le navigateur ne doit jamais « deviner » un autre type que celui annoncé
        "X-Content-Type-Options": "nosniff",
    }
    if correspond(if_none_match, entetes["ETag"], comparaison_faible=True):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=entetes)
    return Response(couverture.contenu, media_type=couverture.type_mime, headers=entetes)


@router_admin.post(
    "",
    response_model=LivreOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        **creation("Livre créé ; l'en-tête Location donne son URL"),
        409: erreur("ISBN déjà utilisé par un autre livre", ISBN_EN_DOUBLE),
    },
)
def ajouter_livre(donnees: LivreCreate, db: SessionDb, request: Request, response: Response) -> Livre:
    """Ajout d'un livre (administrateurs)."""
    livre = Livre(**donnees.model_dump())
    db.add(livre)
    _commit_ou_conflit(db)
    db.refresh(livre)
    response.headers["Location"] = request.app.url_path_for("detail_livre", livre_id=livre.id)
    response.headers["ETag"] = etag_de(LivreOut.model_validate(livre))
    return livre


MODIFIE_ENTRE_TEMPS = "Le livre a été modifié entre-temps : le relire (GET) puis réessayer"


@router_admin.patch(
    "/{livre_id}",
    response_model=LivreOut,
    responses={
        200: {"description": "Livre modifié", "headers": {"ETag": _en_tete("Nouvel ETag du livre")}},
        400: erreur("Aucun champ à modifier dans la requête", "Aucun champ à modifier"),
        **LIVRE_INTROUVABLE,
        409: erreur(
            "Modification incompatible avec l'état du livre",
            ISBN_EN_DOUBLE,
            "Livre emprunté : enregistrer son retour",
        ),
        412: erreur("If-Match ne correspond plus : quelqu'un a modifié le livre depuis la lecture", MODIFIE_ENTRE_TEMPS),
    },
)
def modifier_livre(
    livre_id: int,
    donnees: LivreUpdate,
    db: SessionDb,
    response: Response,
    if_match: Annotated[
        str | None,
        Header(description="ETag lu avant la modification : 412 si le livre a changé depuis (optionnel)"),
    ] = None,
) -> Livre:
    """Modification partielle d'un livre (administrateurs).

    Un livre emprunté ne peut pas être remis disponible : il faut enregistrer son retour.

    **Concurrence optimiste** : envoyer dans `If-Match` l'ETag obtenu avec `GET /v1/books/{id}`.
    Si un autre administrateur a modifié le livre entre-temps, la réponse est `412` et rien
    n'est écrasé.
    """
    modifications = donnees.model_dump(exclude_unset=True)
    if not modifications:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Aucun champ à modifier")
    # Ligne verrouillée jusqu'au commit : personne ne peut la modifier entre la vérification et l'écriture
    livre = _get_livre(db, livre_id, verrouiller=True)
    if if_match is not None and not correspond(
        if_match, etag_de(LivreOut.model_validate(livre)), comparaison_faible=False
    ):
        db.rollback()
        raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, MODIFIE_ENTRE_TEMPS)
    if modifications.get("disponible") and _a_des_emprunts(db, livre_id, en_cours_seulement=True):
        raise HTTPException(status.HTTP_409_CONFLICT, "Livre emprunté : enregistrer son retour")
    for champ, valeur in modifications.items():
        setattr(livre, champ, valeur)
    _commit_ou_conflit(db)
    db.refresh(livre)
    response.headers["ETag"] = etag_de(LivreOut.model_validate(livre))
    return livre


@router_admin.delete(
    "/{livre_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Livre supprimé (réponse sans contenu)"},
        **LIVRE_INTROUVABLE,
        409: erreur(
            "Le livre a un historique d'emprunts",
            "Ce livre a un historique d'emprunts : le rendre indisponible plutôt que le supprimer",
        ),
    },
)
def supprimer_livre(livre_id: int, db: SessionDb) -> None:
    """Suppression d'un livre (administrateurs).

    Refusée si le livre a déjà été emprunté, pour conserver l'historique des utilisateurs :
    le rendre indisponible à la place.
    """
    livre = _get_livre(db, livre_id)
    if _a_des_emprunts(db, livre_id, en_cours_seulement=False):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ce livre a un historique d'emprunts : le rendre indisponible plutôt que le supprimer",
        )
    db.delete(livre)
    db.commit()


@router_admin.put(
    "/{livre_id}/cover",
    response_model=LivreOut,
    responses={
        **LIVRE_INTROUVABLE,
        400: erreur("Fichier vide", "Fichier vide"),
        413: erreur(
            "Image trop volumineuse",
            f"Image trop volumineuse (maximum {couvertures.TAILLE_MAX_COUVERTURE // 1024} Ko)",
        ),
        415: erreur(
            "Le fichier n'est pas une image JPEG, PNG ou WebP",
            "Format non supporté : image JPEG, PNG ou WebP attendue",
        ),
    },
)
def envoyer_couverture(
    livre_id: int,
    fichier: Annotated[UploadFile, File(description="Image JPEG, PNG ou WebP, 500 Ko maximum")],
    db: SessionDb,
) -> Livre:
    """Ajoute ou remplace la couverture d'un livre (administrateurs).

    Le format est vérifié d'après le contenu réel du fichier, pas d'après son nom
    ou le type annoncé : un fichier renommé en `.jpg` est refusé (`415`).
    """
    livre = _get_livre(db, livre_id)
    contenu, type_mime = couvertures.lire_image(fichier.file)
    couvertures.enregistrer(db, livre_id, contenu, type_mime)
    db.refresh(livre)  # met à jour couverture_url
    return livre


@router_admin.delete(
    "/{livre_id}/cover",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Couverture supprimée"},
        404: erreur("Livre introuvable, ou livre sans couverture", "Livre introuvable", "Ce livre n'a pas de couverture"),
    },
)
def supprimer_couverture(livre_id: int, db: SessionDb) -> None:
    """Supprime la couverture d'un livre (administrateurs)."""
    livre = _get_livre(db, livre_id)
    couverture = db.get(Couverture, livre_id)
    if couverture is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ce livre n'a pas de couverture")
    db.delete(couverture)
    db.commit()
    db.expire(livre, ["nb_couvertures"])  # recalculé à la prochaine lecture (couverture_url -> null)
