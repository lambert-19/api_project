from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

from models.utilisateur import RoleUtilisateur

Email = Annotated[EmailStr, AfterValidator(str.lower)]


class UtilisateurCreate(BaseModel):
    """Données d'inscription."""

    nom: str = Field(min_length=1, max_length=100)
    email: Email = Field(max_length=255)
    telephone: str | None = Field(default=None, pattern=r"^\+?[0-9][0-9 .\-]{5,18}$")
    mot_de_passe: str = Field(min_length=8, max_length=128)

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "nom": "Marie Curie",
                    "email": "marie.curie@example.com",
                    "telephone": "+33 6 12 34 56 78",
                    "mot_de_passe": "radium1898",
                }
            ]
        },
    )


class UtilisateurOut(BaseModel):
    """Utilisateur renvoyé par l'API : jamais de mot de passe ni de hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    email: str
    telephone: str | None
    role: RoleUtilisateur
    date_inscription: datetime


class Jeton(BaseModel):
    """Réponse de POST /auth/token (format imposé par OAuth2)."""

    access_token: str
    token_type: str = "bearer"
