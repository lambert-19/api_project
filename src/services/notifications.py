import logging
from datetime import date

logger = logging.getLogger("uvicorn.error")


def confirmer_emprunt(email: str, titre: str, date_retour_prevue: date) -> None:
    """Simule l'envoi d'un mail de confirmation (exécuté après l'envoi de la réponse)."""
    logger.info(
        "Mail envoyé à %s : vous avez emprunté « %s », à rendre avant le %s",
        email,
        titre,
        date_retour_prevue.strftime("%d/%m/%Y"),
    )
