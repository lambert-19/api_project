from fastapi import APIRouter, status

from dependances import AdminCourant, SessionDb, UtilisateurCourant
from models import Emprunt
from schemas.emprunt import EmpruntAdminOut, EmpruntCreate, EmpruntOut
from services import emprunts

router = APIRouter(prefix="/loans", tags=["Emprunts"])


@router.post("", response_model=EmpruntOut, status_code=status.HTTP_201_CREATED)
def emprunter_livre(donnees: EmpruntCreate, utilisateur: UtilisateurCourant, db: SessionDb) -> Emprunt:
    """Emprunte un livre disponible pour 14 jours (5 emprunts en cours maximum)."""
    return emprunts.emprunter(db, utilisateur, donnees.livre_id)


@router.post("/{emprunt_id}/return", response_model=EmpruntOut)
def rendre_livre(emprunt_id: int, utilisateur: UtilisateurCourant, db: SessionDb) -> Emprunt:
    """Enregistre le retour d'un livre (par l'emprunteur ou un administrateur)."""
    return emprunts.rendre(db, utilisateur, emprunt_id)


@router.get("/overdue", response_model=list[EmpruntAdminOut])
def emprunts_en_retard(db: SessionDb, _: AdminCourant) -> list[Emprunt]:
    """Emprunts non rendus dont la date de retour prévue est dépassée (administrateurs)."""
    return emprunts.emprunts_en_retard(db)
