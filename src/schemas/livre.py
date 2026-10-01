from datetime import date
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Titre = Annotated[str, Field(min_length=1, max_length=255)]
Auteur = Annotated[str, Field(min_length=1, max_length=255)]
Genre = Annotated[str, Field(min_length=1, max_length=100)]
Isbn = Annotated[str, Field(pattern=r"^(\d{9}[\dX]|\d{13})$")]


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
