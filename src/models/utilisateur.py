import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Identity, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.emprunt import Emprunt


class RoleUtilisateur(enum.StrEnum):
    ADMIN = "admin"
    MEMBRE = "membre"


class Utilisateur(Base):
    """Personne inscrite à la bibliothèque (membre ou administrateur)."""

    __tablename__ = "utilisateur"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    nom: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    telephone: Mapped[str | None] = mapped_column(String(20))

    mot_de_passe_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[RoleUtilisateur] = mapped_column(

        Enum(
            RoleUtilisateur,
            name="role",
            native_enum=False,
            create_constraint=True,
            length=10,
            values_callable=lambda roles: [r.value for r in roles],
        ),
        default=RoleUtilisateur.MEMBRE,
        server_default=RoleUtilisateur.MEMBRE.value,
    )
    date_inscription: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    emprunts: Mapped[list["Emprunt"]] = relationship(back_populates="utilisateur")
