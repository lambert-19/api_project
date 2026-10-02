from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from config import get_settings
_hasher = PasswordHash.recommended()

_HASH_FACTICE = _hasher.hash("mot-de-passe-factice")


def hasher_mot_de_passe(mot_de_passe: str) -> str:
    return _hasher.hash(mot_de_passe)


def verifier_mot_de_passe(mot_de_passe: str, hash_: str | None) -> bool:
    """Compare un mot de passe à son hash. `hash_=None` (utilisateur inconnu) renvoie toujours False."""
    if hash_ is None:
        _hasher.verify(mot_de_passe, _HASH_FACTICE)
        return False
    return _hasher.verify(mot_de_passe, hash_)


@dataclass(frozen=True)
class JetonLu:
    utilisateur_id: int
    scopes: frozenset[str]


def creer_jeton(utilisateur_id: int, scopes: Iterable[str]) -> str:
    """JWT signé contenant l'id de l'utilisateur (`sub`), ses permissions (`scope`,
    séparées par des espaces, format OAuth2) et sa date d'expiration (`exp`)."""
    settings = get_settings()
    expiration = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {"sub": str(utilisateur_id), "scope": " ".join(sorted(scopes)), "exp": expiration},
        settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm,
    )


def lire_jeton(jeton: str) -> JetonLu | None:
    """Renvoie l'id de l'utilisateur et ses permissions, ou None si le jeton est invalide, falsifié ou expiré."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            jeton,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
            options={"require": ["sub", "exp"]},
        )
        scope = payload.get("scope", "")
        if not isinstance(scope, str):
            return None
        return JetonLu(int(payload["sub"]), frozenset(scope.split()))
    except (jwt.InvalidTokenError, ValueError):
        return None
