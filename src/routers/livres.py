from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status
from sqlalchemy import ColumnElement, exists, func, select
from sqlalchemy.exc import IntegrityError

from dependances import GestionnaireLivres, SessionDb
from etag import correspond, etag_de
from models import Emprunt, Livre
from reponses import LIVRE_INTROUVABLE, creation, erreur, permission_requise
from schemas.livre import FiltresLivres, LivreCreate, LivreOut, LivreUpdate

router = APIRouter(prefix="/books", tags=["Livres"])

ISBN_EN_DOUBLE = "Un livre avec cet ISBN existe déjà"
ECRITURE_LIVRES = permission_requise("livres:ecrire")


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


@router.post(
    "",
    response_model=LivreOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        **creation("Livre créé ; l'en-tête Location donne son URL"),
        **ECRITURE_LIVRES,
        409: erreur("ISBN déjà utilisé par un autre livre", ISBN_EN_DOUBLE),
    },
)
def ajouter_livre(
    donnees: LivreCreate, db: SessionDb, _: GestionnaireLivres, request: Request, response: Response
) -> Livre:
    """Ajout d'un livre (administrateurs)."""
    livre = Livre(**donnees.model_dump())
    db.add(livre)
    _commit_ou_conflit(db)
    db.refresh(livre)
    response.headers["Location"] = request.app.url_path_for("detail_livre", livre_id=livre.id)
    response.headers["ETag"] = etag_de(LivreOut.model_validate(livre))
    return livre


MODIFIE_ENTRE_TEMPS = "Le livre a été modifié entre-temps : le relire (GET) puis réessayer"


@router.patch(
    "/{livre_id}",
    response_model=LivreOut,
    responses={
        200: {"description": "Livre modifié", "headers": {"ETag": _en_tete("Nouvel ETag du livre")}},
        400: erreur("Aucun champ à modifier dans la requête", "Aucun champ à modifier"),
        **ECRITURE_LIVRES,
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
    _: GestionnaireLivres,
    response: Response,
    if_match: Annotated[
        str | None,
        Header(description="ETag lu avant la modification : 412 si le livre a changé depuis (optionnel)"),
    ] = None,
) -> Livre:
    """Modification partielle d'un livre (administrateurs).

    Un livre emprunté ne peut pas être remis disponible : il faut enregistrer son retour.

    **Concurrence optimiste** : envoyer dans `If-Match` l'ETag obtenu avec `GET /books/{id}`.
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


@router.delete(
    "/{livre_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Livre supprimé (réponse sans contenu)"},
        **ECRITURE_LIVRES,
        **LIVRE_INTROUVABLE,
        409: erreur(
            "Le livre a un historique d'emprunts",
            "Ce livre a un historique d'emprunts : le rendre indisponible plutôt que le supprimer",
        ),
    },
)
def supprimer_livre(livre_id: int, db: SessionDb, _: GestionnaireLivres) -> None:
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
