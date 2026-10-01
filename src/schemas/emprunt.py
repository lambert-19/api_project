from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class LivreResume(BaseModel):
    """Informations du livre affichées dans un emprunt."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    titre: str
    auteur: str


class EmpruntOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    livre: LivreResume
    date_emprunt: datetime
    date_retour_prevue: date
    date_retour: datetime | None


class UtilisateurResume(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    email: str


class EmpruntAdminOut(EmpruntOut):
    utilisateur: UtilisateurResume


class EmpruntCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"livre_id": 1}]})

    livre_id: int
