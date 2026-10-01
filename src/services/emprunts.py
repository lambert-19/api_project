from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import Emprunt, Livre, RoleUtilisateur, Utilisateur

DUREE_EMPRUNT_JOURS = 14
MAX_EMPRUNTS_EN_COURS = 5


def emprunter(db: Session, utilisateur: Utilisateur, livre_id: int) -> Emprunt:
    """Crée l'emprunt et rend le livre indisponible, dans une seule transaction.

    Le SELECT ... FOR UPDATE verrouille la ligne du livre jusqu'au commit : si deux
    utilisateurs empruntent le même livre en même temps, le second attend puis voit
    le livre indisponible.
    """
    livre = db.scalar(select(Livre).where(Livre.id == livre_id).with_for_update())
    if livre is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Livre introuvable")
    if not livre.disponible:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Livre déjà emprunté ou indisponible")

    en_cours = db.scalar(
        select(func.count())
        .select_from(Emprunt)
        .where(Emprunt.utilisateur_id == utilisateur.id, Emprunt.date_retour.is_(None))
    )
    if en_cours >= MAX_EMPRUNTS_EN_COURS:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Limite de {MAX_EMPRUNTS_EN_COURS} emprunts en cours atteinte",
        )

    emprunt = Emprunt(
        utilisateur=utilisateur,
        livre=livre,
        date_retour_prevue=date.today() + timedelta(days=DUREE_EMPRUNT_JOURS),
    )
    livre.disponible = False
    db.add(emprunt)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Livre déjà emprunté ou indisponible")
    db.refresh(emprunt)
    return emprunt


def rendre(db: Session, utilisateur: Utilisateur, emprunt_id: int) -> Emprunt:
    """Enregistre le retour et rend le livre de nouveau disponible, dans une seule transaction.

    Seul l'emprunteur ou un administrateur peut enregistrer le retour.
    """
    emprunt = db.scalar(select(Emprunt).where(Emprunt.id == emprunt_id).with_for_update())
    if emprunt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emprunt introuvable")
    if emprunt.utilisateur_id != utilisateur.id and utilisateur.role != RoleUtilisateur.ADMIN:
        db.rollback()
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cet emprunt ne vous appartient pas")
    if emprunt.date_retour is not None:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce livre a déjà été rendu")

    emprunt.date_retour = func.current_timestamp()
    emprunt.livre.disponible = True
    db.commit()
    db.refresh(emprunt)
    return emprunt


def emprunts_en_retard(db: Session) -> list[Emprunt]:
    return list(
        db.scalars(
            select(Emprunt)
            .where(Emprunt.date_retour.is_(None), Emprunt.date_retour_prevue < date.today())
            .order_by(Emprunt.date_retour_prevue)
        )
    )
