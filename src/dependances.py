from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.params import Security as SecurityParam
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from sqlalchemy.orm import Session

from config import PREFIXE_API
from database import get_db
from models import RoleUtilisateur, Utilisateur
from permissions import SCOPES, scopes_autorises
from security import lire_jeton

# `scopes` : affichés dans la fenêtre Authorize de Swagger, où on peut les cocher
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{PREFIXE_API}/auth/token", scopes=SCOPES)

SessionDb = Annotated[Session, Depends(get_db)]
JetonBrut = Annotated[str, Depends(oauth2_scheme)]


def _authentifier(jeton: str, db: Session) -> tuple[Utilisateur, frozenset[str]]:
    """Utilisateur du jeton et permissions effectives, sinon 401."""
    lu = lire_jeton(jeton)
    utilisateur = db.get(Utilisateur, lu.utilisateur_id) if lu is not None else None
    if lu is None or utilisateur is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Jeton invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Recoupées avec le rôle ACTUEL : un admin rétrogradé perd ses droits
    # immédiatement, sans attendre l'expiration de son jeton
    return utilisateur, lu.scopes & scopes_autorises(utilisateur.role)


def get_current_user(security_scopes: SecurityScopes, jeton: JetonBrut, db: SessionDb) -> Utilisateur:
    """Utilisateur authentifié dont le jeton contient les permissions demandées par la route.

    `security_scopes.scopes` : permissions déclarées avec Security(..., scopes=[...]).
    Jeton absent ou invalide -> 401 ; permission manquante -> 403.
    """
    utilisateur, accordes = _authentifier(jeton, db)
    manquants = [scope for scope in security_scopes.scopes if scope not in accordes]
    if manquants:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Permission insuffisante : {', '.join(manquants)} requis",
            headers={"WWW-Authenticate": f'Bearer error="insufficient_scope", scope="{security_scopes.scope_str}"'},
        )
    return utilisateur


def get_scopes_accordes(jeton: JetonBrut, db: SessionDb) -> frozenset[str]:
    """Permissions effectives du jeton, pour les routes dont le comportement en dépend."""
    return _authentifier(jeton, db)[1]


def permission(scope: str) -> SecurityParam:
    """Exige une permission, pour `APIRouter(dependencies=[permission("...")])` : toutes les
    routes du routeur sont protégées d'un coup, sans paramètre à ajouter dans chaque fonction."""
    return Security(get_current_user, scopes=[scope])


def exiger_role_admin(utilisateur: Annotated[Utilisateur, Security(get_current_user)]) -> None:
    """Protection de tout le routeur /admin : rôle administrateur exigé, quel que soit le jeton."""
    if utilisateur.role != RoleUtilisateur.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux administrateurs")


# Routes qui ont besoin de l'utilisateur lui-même : la permission est déclarée dans le paramètre
Profil = Annotated[Utilisateur, Security(get_current_user, scopes=["profil"])]
Emprunteur = Annotated[Utilisateur, Security(get_current_user, scopes=["emprunts"])]
ScopesAccordes = Annotated[frozenset[str], Depends(get_scopes_accordes)]
