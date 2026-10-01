from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError

from dependances import AdminCourant, SessionDb
from models import Emprunt, Livre
from schemas.livre import LivreCreate, LivreOut, LivreUpdate

router = APIRouter(prefix="/books", tags=["Livres"])


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
        raise HTTPException(status.HTTP_409_CONFLICT, "Un livre avec cet ISBN existe déjà")


@router.get("", response_model=list[LivreOut])
def rechercher_livres(
    db: SessionDb,
    title: Annotated[str | None, Query(min_length=1, max_length=255, description="Partie du titre")] = None,
    author: Annotated[str | None, Query(min_length=1, max_length=255, description="Partie du nom de l'auteur")] = None,
    genre: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    available: Annotated[bool | None, Query(description="Uniquement les livres disponibles (true) ou empruntés (false)")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[Livre]:
    """Recherche par titre, auteur ou genre (insensible à la casse), avec pagination."""
    requete = select(Livre)
    if title:
        requete = requete.where(func.lower(Livre.titre).contains(title.lower()))
    if author:
        requete = requete.where(func.lower(Livre.auteur).contains(author.lower()))
    if genre:
        requete = requete.where(func.lower(Livre.genre) == genre.lower())
    if available is not None:
        requete = requete.where(Livre.disponible == available)
    requete = requete.order_by(Livre.titre, Livre.id).offset(skip).limit(limit)
    return list(db.scalars(requete))


@router.get("/{livre_id}", response_model=LivreOut)
def detail_livre(livre_id: int, db: SessionDb) -> Livre:
    """Informations détaillées d'un livre."""
    return _get_livre(db, livre_id)


@router.post("", response_model=LivreOut, status_code=status.HTTP_201_CREATED)
def ajouter_livre(donnees: LivreCreate, db: SessionDb, _: AdminCourant) -> Livre:
    """Ajout d'un livre (administrateurs)."""
    livre = Livre(**donnees.model_dump())
    db.add(livre)
    _commit_ou_conflit(db)
    db.refresh(livre)
    return livre


@router.patch("/{livre_id}", response_model=LivreOut)
def modifier_livre(livre_id: int, donnees: LivreUpdate, db: SessionDb, _: AdminCourant) -> Livre:
    """Modification partielle d'un livre (administrateurs).

    Un livre emprunté ne peut pas être remis disponible : il faut enregistrer son retour.
    """
    livre = _get_livre(db, livre_id)
    modifications = donnees.model_dump(exclude_unset=True)
    if modifications.get("disponible") and _a_des_emprunts(db, livre_id, en_cours_seulement=True):
        raise HTTPException(status.HTTP_409_CONFLICT, "Livre emprunté : enregistrer son retour")
    for champ, valeur in modifications.items():
        setattr(livre, champ, valeur)
    _commit_ou_conflit(db)
    db.refresh(livre)
    return livre


@router.delete("/{livre_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_livre(livre_id: int, db: SessionDb, _: AdminCourant) -> None:
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
