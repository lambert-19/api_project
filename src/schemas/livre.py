from datetime import date
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Titre = Annotated[str, Field(min_length=1, max_length=255)]
Auteur = Annotated[str, Field(min_length=1, max_length=255)]
Genre = Annotated[str, Field(min_length=1, max_length=100)]
Isbn = Annotated[str, Field(pattern=r"^(\d{9}[\dX]|\d{13})$")]


class FiltresLivres(BaseModel):
    """Paramètres de recherche de GET /books, regroupés dans un modèle.

    📖 Doc FastAPI : Query Parameter Models. `extra="forbid"` : un paramètre inconnu
    (ex. `?titel=dune`) est refusé en 422 au lieu d'être ignoré sans prévenir.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=255, description="Partie du titre")
    author: str | None = Field(default=None, min_length=1, max_length=255, description="Partie du nom de l'auteur")
    genre: str | None = Field(default=None, min_length=1, max_length=100, description="Genre exact")
    available: bool | None = Field(
        default=None, description="Uniquement les livres disponibles (true) ou empruntés (false)"
    )
    skip: int = Field(default=0, ge=0, description="Nombre de résultats à sauter (pagination)")
    limit: int = Field(default=20, ge=1, le=100, description="Nombre maximum de résultats")


class LivreCreate(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "titre": "Dune",
                    "auteur": "Frank Herbert",
                    "genre": "Science-fiction",
                    "date_publication": "1965-08-01",
                    "isbn": "9782266320481",
                }
            ]
        },
    )

    titre: Titre
    auteur: Auteur
    genre: Genre | None = None
    date_publication: date | None = None
    isbn: Isbn | None = None


class LivreUpdate(BaseModel):
    """Seuls les champs envoyés sont modifiés."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={"examples": [{"genre": "Roman", "disponible": False}]},
    )

    titre: Titre | None = None
    auteur: Auteur | None = None
    genre: Genre | None = None
    date_publication: date | None = None
    isbn: Isbn | None = None
    disponible: bool | None = None

    @model_validator(mode="after")
    def champs_obligatoires_non_nuls(self) -> Self:
        for champ in ("titre", "auteur", "disponible"):
            if champ in self.model_fields_set and getattr(self, champ) is None:
                raise ValueError(f"{champ} ne peut pas être null")
        return self


class LivreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    titre: str
    auteur: str
    genre: str | None
    date_publication: date | None
    isbn: str | None
    disponible: bool
