from datetime import date

from fastapi import APIRouter, BackgroundTasks, status
from fastapi.responses import StreamingResponse

from dependances import Emprunteur, ScopesAccordes, SessionDb, permission
from models import Emprunt
from reponses import NON_AUTHENTIFIE, admin_requis, erreur, permission_requise
from schemas.emprunt import EmpruntAdminOut, EmpruntCreate, EmpruntOut
from services import emprunts, export
from services.emprunts import MAX_EMPRUNTS_EN_COURS
from services.notifications import confirmer_emprunt

# Emprunts de l'utilisateur connecté : /v1/loans
router = APIRouter(prefix="/loans", tags=["Emprunts"])

# Supervision de tous les emprunts : /v1/admin/loans (inclus dans routers/admin.py),
# permission exigée une seule fois pour tout le routeur
router_admin = APIRouter(
    prefix="/loans",
    dependencies=[permission("emprunts:gerer")],
    responses=admin_requis("emprunts:gerer"),
)


@router.post(
    "",
    response_model=EmpruntOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        **permission_requise("emprunts"),
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
    utilisateur: Emprunteur,
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
        403: erreur(
            "Permission manquante, ou emprunt d'un autre utilisateur sans la permission emprunts:gerer",
            "Permission insuffisante : emprunts requis",
            "Cet emprunt ne vous appartient pas",
        ),
        404: erreur("Aucun emprunt avec cet identifiant", "Emprunt introuvable"),
        409: erreur("Le livre est déjà rendu", "Ce livre a déjà été rendu"),
    },
)
def rendre_livre(emprunt_id: int, utilisateur: Emprunteur, scopes: ScopesAccordes, db: SessionDb) -> Emprunt:
    """Enregistre le retour d'un livre : par l'emprunteur, ou par un utilisateur ayant
    la permission `emprunts:gerer` (administrateurs)."""
    return emprunts.rendre(db, utilisateur, emprunt_id, gere_tous_les_emprunts="emprunts:gerer" in scopes)


@router_admin.get("/overdue", response_model=list[EmpruntAdminOut])
def emprunts_en_retard(db: SessionDb) -> list[Emprunt]:
    """Emprunts non rendus dont la date de retour prévue est dépassée (administrateurs)."""
    return emprunts.emprunts_en_retard(db)


@router_admin.get(
    "/export",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Fichier CSV de tous les emprunts (séparateur « ; », UTF-8), téléchargé en pièce jointe",
            "content": {
                "text/csv": {
                    "example": "id;emprunteur;email;livre;isbn;date_emprunt;date_retour_prevue;date_retour;statut\n"
                    "1;Marie Curie;marie.curie@example.com;Dune;9782266320481;2026-10-01 10:00:00;2026-10-15;;en cours\n"
                }
            },
        },
    },
)
def exporter_emprunts(db: SessionDb) -> StreamingResponse:
    """Export CSV de tous les emprunts (administrateurs), avec leur statut : en cours, en retard ou rendu.

    Le fichier est envoyé ligne par ligne (`StreamingResponse`), sans être construit en mémoire.
    """
    return StreamingResponse(
        export.lignes_csv(db),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="emprunts_{date.today().isoformat()}.csv"'},
    )
