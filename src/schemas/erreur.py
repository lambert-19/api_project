"""Format des réponses d'erreur, affiché dans la documentation Swagger."""

from pydantic import BaseModel, Field


class Erreur(BaseModel):
    """Réponse d'erreur standard (400, 401, 403, 404, 405, 409, 412, 413, 415, 429, 500, 503)."""

    detail: str = Field(description="Message d'erreur lisible")


class ChampInvalide(BaseModel):
    emplacement: str = Field(description="Où se trouve le champ : body, query, path, header", examples=["body"])
    champ: str | None = Field(description="Nom du champ en erreur (vide si l'erreur concerne tout le corps)", examples=["email"])
    message: str = Field(examples=["Adresse email invalide"])


class ErreurValidation(BaseModel):
    """Réponse 422 : données envoyées invalides, avec le détail de chaque champ."""

    detail: str = Field(examples=["Données invalides"])
    erreurs: list[ChampInvalide]
