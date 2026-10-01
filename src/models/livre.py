from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Identity, String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.emprunt import Emprunt


class Livre(Base):
    """Ouvrage de l'inventaire."""

    __tablename__ = "livre"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    titre: Mapped[str] = mapped_column(String(255), index=True)
    auteur: Mapped[str] = mapped_column(String(255), index=True)
    genre: Mapped[str | None] = mapped_column(String(100), index=True)
    date_publication: Mapped[date | None] = mapped_column(Date)
    isbn: Mapped[str | None] = mapped_column(String(13), unique=True)
    disponible: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    emprunts: Mapped[list["Emprunt"]] = relationship(back_populates="livre")
