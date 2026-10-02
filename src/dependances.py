from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from sqlalchemy.orm import Session

from database import get_db
from models import Utilisateur
from permissions import SCOPES, scopes_autorises
from security import lire_jeton

# `scopes` : affichés dans la fenêtre Authorize de Swagger, où on peut les cocher
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", scopes=SCOPES)

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


# Une permission par usage : la route déclare ce dont elle a besoin
Profil = Annotated[Utilisateur, Security(get_current_user, scopes=["profil"])]
Emprunteur = Annotated[Utilisateur, Security(get_current_user, scopes=["emprunts"])]
GestionnaireLivres = Annotated[Utilisateur, Security(get_current_user, scopes=["livres:ecrire"])]
GestionnaireEmprunts = Annotated[Utilisateur, Security(get_current_user, scopes=["emprunts:gerer"])]
ScopesAccordes = Annotated[frozenset[str], Depends(get_scopes_accordes)]
