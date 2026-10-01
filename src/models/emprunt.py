from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    case,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base
from models.livre import Livre
from models.utilisateur import Utilisateur


class Emprunt(Base):
    """Emprunt d'un livre par un utilisateur. Conservé après le retour (historique)."""

    __tablename__ = "emprunt"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    utilisateur_id: Mapped[int] = mapped_column(ForeignKey("utilisateur.id"), index=True)
    livre_id: Mapped[int] = mapped_column(ForeignKey("livre.id"), index=True)
    date_emprunt: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    date_retour_prevue: Mapped[date] = mapped_column(Date)
    date_retour: Mapped[datetime | None] = mapped_column(DateTime)

    utilisateur: Mapped[Utilisateur] = relationship(back_populates="emprunts")
    livre: Mapped[Livre] = relationship(back_populates="emprunts")

    __table_args__ = (
        CheckConstraint(
            "date_retour IS NULL OR date_retour >= date_emprunt",
            name="dates_coherentes",
        ),
    )

Index(
    "uq_emprunt_livre_en_cours",
    case((Emprunt.date_retour.is_(None), Emprunt.livre_id)),
    unique=True,
)
