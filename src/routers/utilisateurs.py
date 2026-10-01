from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from dependances import SessionDb, UtilisateurCourant
from models import Emprunt, Utilisateur
from schemas.emprunt import EmpruntOut
from schemas.utilisateur import UtilisateurCreate, UtilisateurOut
from security import hasher_mot_de_passe

router = APIRouter(prefix="/users", tags=["Utilisateurs"])


@router.post("/register", response_model=UtilisateurOut, status_code=status.HTTP_201_CREATED)
def inscription(donnees: UtilisateurCreate, db: SessionDb) -> Utilisateur:
    """Inscription d'un nouveau membre. Le rôle admin ne peut pas être choisi ici."""
    utilisateur = Utilisateur(
        nom=donnees.nom,
        email=donnees.email,
        telephone=donnees.telephone,
        mot_de_passe_hash=hasher_mot_de_passe(donnees.mot_de_passe),
    )
    db.add(utilisateur)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Cet email est déjà utilisé")
    db.refresh(utilisateur)
    return utilisateur


@router.get("/me", response_model=UtilisateurOut)
def mon_profil(utilisateur: UtilisateurCourant) -> Utilisateur:
    """Profil de l'utilisateur connecté."""
    return utilisateur


def _mes_emprunts(db: SessionDb, utilisateur: Utilisateur, en_cours: bool) -> list[Emprunt]:
    requete = (
        select(Emprunt)
        .options(joinedload(Emprunt.livre))
        .where(Emprunt.utilisateur_id == utilisateur.id)
        .order_by(Emprunt.date_emprunt.desc())
    )
    if en_cours:
        requete = requete.where(Emprunt.date_retour.is_(None))
    return list(db.scalars(requete))


@router.get("/me/loans", response_model=list[EmpruntOut])
def mes_emprunts_en_cours(utilisateur: UtilisateurCourant, db: SessionDb) -> list[Emprunt]:
    """Emprunts en cours (livres pas encore rendus)."""
    return _mes_emprunts(db, utilisateur, en_cours=True)


@router.get("/me/history", response_model=list[EmpruntOut])
def mon_historique(utilisateur: UtilisateurCourant, db: SessionDb) -> list[Emprunt]:
    """Historique complet des emprunts, du plus récent au plus ancien."""
    return _mes_emprunts(db, utilisateur, en_cours=False)
