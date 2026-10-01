from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database import get_db
from models import RoleUtilisateur, Utilisateur
from security import lire_jeton
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

SessionDb = Annotated[Session, Depends(get_db)]


def get_current_user(jeton: Annotated[str, Depends(oauth2_scheme)], db: SessionDb) -> Utilisateur:
    """Utilisateur authentifié par le jeton JWT, sinon 401."""
    utilisateur_id = lire_jeton(jeton)
    utilisateur = db.get(Utilisateur, utilisateur_id) if utilisateur_id is not None else None
    if utilisateur is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Jeton invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return utilisateur


UtilisateurCourant = Annotated[Utilisateur, Depends(get_current_user)]


def get_current_admin(utilisateur: UtilisateurCourant) -> Utilisateur:
    """Utilisateur authentifié ET administrateur, sinon 403."""
    if utilisateur.role != RoleUtilisateur.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux administrateurs")
    return utilisateur


AdminCourant = Annotated[Utilisateur, Depends(get_current_admin)]
