from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from dependances import SessionDb
from limiteur import limiteur_connexion
from models import Utilisateur
from reponses import erreur
from schemas.utilisateur import Jeton
from security import creer_jeton, verifier_mot_de_passe

router = APIRouter(prefix="/auth", tags=["Authentification"])


@router.post(
    "/token",
    response_model=Jeton,
    responses={
        401: erreur("Identifiants incorrects", "Email ou mot de passe incorrect"),
        429: {
            **erreur(
                "Trop d'échecs de connexion depuis cette adresse IP",
                "Trop de tentatives de connexion, réessayez dans 42 secondes",
            ),
            "headers": {
                "Retry-After": {"description": "Secondes à attendre avant de réessayer", "schema": {"type": "integer"}}
            },
        },
    },
)
def connexion(
    request: Request,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: SessionDb,
) -> Jeton:
    """Connexion : le champ `username` contient l'email. Renvoie un jeton JWT à envoyer
    ensuite dans l'en-tête `Authorization: Bearer <jeton>`.

    Après 5 échecs en une minute depuis la même adresse IP, les tentatives sont refusées (429).
    """
    ip = request.client.host if request.client else "inconnue"
    attente = limiteur_connexion.attente(ip)
    if attente:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Trop de tentatives de connexion, réessayez dans {attente} secondes",
            headers={"Retry-After": str(attente)},
        )

    utilisateur = db.scalar(select(Utilisateur).where(Utilisateur.email == form.username.strip().lower()))
    hash_ = utilisateur.mot_de_passe_hash if utilisateur else None
    if not verifier_mot_de_passe(form.password, hash_) or utilisateur is None:
        limiteur_connexion.enregistrer_echec(ip)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Jeton(access_token=creer_jeton(utilisateur.id))
