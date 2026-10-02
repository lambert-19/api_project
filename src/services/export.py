"""Export CSV des emprunts, produit ligne par ligne.

📖 Doc FastAPI : Custom Response → StreamingResponse

Le fichier n'est jamais construit en entier en mémoire : chaque ligne est envoyée au
client dès qu'elle est lue en base (par lots de 500 avec yield_per). L'export reste
léger même avec des centaines de milliers d'emprunts.
"""

import csv
import io
from collections.abc import Iterator
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from models import Emprunt

COLONNES = [
    "id", "emprunteur", "email", "livre", "isbn",
    "date_emprunt", "date_retour_prevue", "date_retour", "statut",
]


def _statut(emprunt: Emprunt, aujourd_hui: date) -> str:
    if emprunt.date_retour is not None:
        return "rendu"
    return "en retard" if emprunt.date_retour_prevue < aujourd_hui else "en cours"


def lignes_csv(db: Session) -> Iterator[str]:
    """Génère le CSV ligne par ligne (séparateur « ; » et BOM UTF-8 : s'ouvre directement dans Excel)."""
    tampon = io.StringIO()
    ecrivain = csv.writer(tampon, delimiter=";")

    def ligne(valeurs: list) -> str:
        ecrivain.writerow(valeurs)
        texte = tampon.getvalue()
        tampon.seek(0)
        tampon.truncate()
        return texte

    yield "﻿" + ligne(COLONNES)

    aujourd_hui = date.today()
    requete = (
        select(Emprunt)
        .options(joinedload(Emprunt.utilisateur), joinedload(Emprunt.livre))
        .order_by(Emprunt.id)
        .execution_options(yield_per=500)
    )
    for emprunt in db.scalars(requete):
        yield ligne([
            emprunt.id,
            emprunt.utilisateur.nom,
            emprunt.utilisateur.email,
            emprunt.livre.titre,
            emprunt.livre.isbn or "",
            emprunt.date_emprunt.isoformat(sep=" ", timespec="seconds"),
            emprunt.date_retour_prevue.isoformat(),
            emprunt.date_retour.isoformat(sep=" ", timespec="seconds") if emprunt.date_retour else "",
            _statut(emprunt, aujourd_hui),
        ])
