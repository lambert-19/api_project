from fastapi import APIRouter, BackgroundTasks, status

from dependances import AdminCourant, SessionDb, UtilisateurCourant
from models import Emprunt
from reponses import ADMIN_REQUIS, NON_AUTHENTIFIE, erreur
from schemas.emprunt import EmpruntAdminOut, EmpruntCreate, EmpruntOut
from services import emprunts
from services.emprunts import MAX_EMPRUNTS_EN_COURS
from services.notifications import confirmer_emprunt

router = APIRouter(prefix="/loans", tags=["Emprunts"])


@router.post(
    "",
    response_model=EmpruntOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        **NON_AUTHENTIFIE,
        404: erreur("Aucun livre avec cet identifiant", "Livre introuvable"),
        409: erreur(
            "Emprunt impossible",
            "Livre déjà emprunté ou indisponible",
            f"Limite de {MAX_EMPRUNTS_EN_COURS} emprunts en cours atteinte",
        ),
    },
)
def emprunter_livre(
    donnees: EmpruntCreate,
    utilisateur: UtilisateurCourant,
    db: SessionDb,
    taches: BackgroundTasks,
) -> Emprunt:
    """Emprunte un livre disponible pour 14 jours (5 emprunts en cours maximum).

    Un mail de confirmation est envoyé en arrière-plan.
    """
    emprunt = emprunts.emprunter(db, utilisateur, donnees.livre_id)
    taches.add_task(confirmer_emprunt, utilisateur.email, emprunt.livre.titre, emprunt.date_retour_prevue)
    return emprunt


@router.post(
    "/{emprunt_id}/return",
    response_model=EmpruntOut,
    responses={
        **NON_AUTHENTIFIE,
        403: erreur("L'emprunt appartient à un autre utilisateur", "Cet emprunt ne vous appartient pas"),
        404: erreur("Aucun emprunt avec cet identifiant", "Emprunt introuvable"),
        409: erreur("Le livre est déjà rendu", "Ce livre a déjà été rendu"),
    },
)
def rendre_livre(emprunt_id: int, utilisateur: UtilisateurCourant, db: SessionDb) -> Emprunt:
    """Enregistre le retour d'un livre (par l'emprunteur ou un administrateur)."""
    return emprunts.rendre(db, utilisateur, emprunt_id)


@router.get("/overdue", response_model=list[EmpruntAdminOut], responses=ADMIN_REQUIS)
def emprunts_en_retard(db: SessionDb, _: AdminCourant) -> list[Emprunt]:
    """Emprunts non rendus dont la date de retour prévue est dépassée (administrateurs)."""
    return emprunts.emprunts_en_retard(db)
