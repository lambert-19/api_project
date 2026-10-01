from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from dependances import SessionDb
from models import Utilisateur
from schemas.utilisateur import Jeton
from security import creer_jeton, verifier_mot_de_passe

router = APIRouter(prefix="/auth", tags=["Authentification"])


@router.post("/token", response_model=Jeton)
def connexion(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: SessionDb) -> Jeton:
    """Connexion : le champ `username` contient l'email. Renvoie un jeton JWT à envoyer
    ensuite dans l'en-tête `Authorization: Bearer <jeton>`."""
    utilisateur = db.scalar(select(Utilisateur).where(Utilisateur.email == form.username.strip().lower()))
    hash_ = utilisateur.mot_de_passe_hash if utilisateur else None
    if not verifier_mot_de_passe(form.password, hash_) or utilisateur is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Jeton(access_token=creer_jeton(utilisateur.id))
