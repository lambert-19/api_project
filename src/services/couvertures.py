"""Couvertures de livres : vérification du fichier envoyé et enregistrement.

📖 Doc FastAPI : Request Files (UploadFile)

Le format est déterminé d'après les premiers octets du fichier (sa « signature »),
jamais d'après le nom ou le Content-Type annoncés par le client, qui peuvent mentir.
Seuls JPEG, PNG et WebP sont acceptés : pas de SVG, qui peut contenir du JavaScript.
"""

from typing import BinaryIO

from fastapi import status
from sqlalchemy.orm import Session

from exceptions import ErreurMetier
from models import Couverture

TAILLE_MAX_COUVERTURE = 500 * 1024  # 500 Ko


class FichierTropGros(ErreurMetier):
    statut = status.HTTP_413_CONTENT_TOO_LARGE


class FormatNonSupporte(ErreurMetier):
    statut = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE


class FichierVide(ErreurMetier):
    statut = status.HTTP_400_BAD_REQUEST


def type_image(contenu: bytes) -> str | None:
    """Type MIME d'après la signature du fichier, ou None si ce n'est pas une image acceptée."""
    if contenu.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if contenu.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if contenu[:4] == b"RIFF" and contenu[8:12] == b"WEBP":
        return "image/webp"
    return None


def lire_image(fichier: BinaryIO) -> tuple[bytes, str]:
    """Lit le fichier envoyé (au plus 500 Ko + 1 octet) et renvoie (contenu, type MIME)."""
    contenu = fichier.read(TAILLE_MAX_COUVERTURE + 1)
    if not contenu:
        raise FichierVide("Fichier vide")
    if len(contenu) > TAILLE_MAX_COUVERTURE:
        raise FichierTropGros(f"Image trop volumineuse (maximum {TAILLE_MAX_COUVERTURE // 1024} Ko)")
    type_mime = type_image(contenu)
    if type_mime is None:
        raise FormatNonSupporte("Format non supporté : image JPEG, PNG ou WebP attendue")
    return contenu, type_mime


def enregistrer(db: Session, livre_id: int, contenu: bytes, type_mime: str) -> None:
    """Crée ou remplace la couverture du livre."""
    couverture = db.get(Couverture, livre_id)
    if couverture is None:
        db.add(Couverture(livre_id=livre_id, contenu=contenu, type_mime=type_mime, taille=len(contenu)))
    else:
        couverture.contenu, couverture.type_mime, couverture.taille = contenu, type_mime, len(contenu)
    db.commit()
