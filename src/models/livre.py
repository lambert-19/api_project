from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Identity, String, func, select, true
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from models.base import Base
from models.couverture import Couverture

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

    # 1 si le livre a une couverture, 0 sinon : calculé par une sous-requête dans le même
    # SELECT, sans charger l'image (pas de colonne en base, pas de requête en plus)
    nb_couvertures: Mapped[int] = column_property(
        select(func.count())
        .where(Couverture.livre_id == id)
        .correlate_except(Couverture)
        .scalar_subquery()
    )
