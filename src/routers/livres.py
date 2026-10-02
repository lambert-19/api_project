from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError

from dependances import GestionnaireLivres, SessionDb
from models import Emprunt, Livre
from reponses import LIVRE_INTROUVABLE, creation, erreur, permission_requise
from schemas.livre import FiltresLivres, LivreCreate, LivreOut, LivreUpdate

router = APIRouter(prefix="/books", tags=["Livres"])

ISBN_EN_DOUBLE = "Un livre avec cet ISBN existe déjà"
ECRITURE_LIVRES = permission_requise("livres:ecrire")


def _get_livre(db: SessionDb, livre_id: int) -> Livre:
    livre = db.get(Livre, livre_id)
    if livre is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Livre introuvable")
    return livre


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


@router.get("", response_model=list[LivreOut])
def rechercher_livres(db: SessionDb, filtres: Annotated[FiltresLivres, Query()]) -> list[Livre]:
    """Recherche par titre, auteur ou genre (insensible à la casse), avec pagination.

    Un paramètre inconnu (faute de frappe comme `titel`) est refusé en 422 au lieu d'être ignoré.
    """
    requete = select(Livre)
    if filtres.title:
        requete = requete.where(func.lower(Livre.titre).contains(filtres.title.lower()))
    if filtres.author:
        requete = requete.where(func.lower(Livre.auteur).contains(filtres.author.lower()))
    if filtres.genre:
        requete = requete.where(func.lower(Livre.genre) == filtres.genre.lower())
    if filtres.available is not None:
        requete = requete.where(Livre.disponible == filtres.available)
    requete = requete.order_by(Livre.titre, Livre.id).offset(filtres.skip).limit(filtres.limit)
    return list(db.scalars(requete))


@router.get("/{livre_id}", response_model=LivreOut, responses=LIVRE_INTROUVABLE)
def detail_livre(livre_id: int, db: SessionDb) -> Livre:
    """Informations détaillées d'un livre."""
    return _get_livre(db, livre_id)


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
    return livre


@router.patch(
    "/{livre_id}",
    response_model=LivreOut,
    responses={
        400: erreur("Aucun champ à modifier dans la requête", "Aucun champ à modifier"),
        **ECRITURE_LIVRES,
        **LIVRE_INTROUVABLE,
        409: erreur(
            "Modification incompatible avec l'état du livre",
            ISBN_EN_DOUBLE,
            "Livre emprunté : enregistrer son retour",
        ),
    },
)
def modifier_livre(livre_id: int, donnees: LivreUpdate, db: SessionDb, _: GestionnaireLivres) -> Livre:
    """Modification partielle d'un livre (administrateurs).

    Un livre emprunté ne peut pas être remis disponible : il faut enregistrer son retour.
    """
    modifications = donnees.model_dump(exclude_unset=True)
    if not modifications:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Aucun champ à modifier")
    livre = _get_livre(db, livre_id)
    if modifications.get("disponible") and _a_des_emprunts(db, livre_id, en_cours_seulement=True):
        raise HTTPException(status.HTTP_409_CONFLICT, "Livre emprunté : enregistrer son retour")
    for champ, valeur in modifications.items():
        setattr(livre, champ, valeur)
    _commit_ou_conflit(db)
    db.refresh(livre)
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
