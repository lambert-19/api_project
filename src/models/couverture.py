from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Couverture(Base):
    """Image de couverture d'un livre (au plus une par livre).

    Dans une table séparée plutôt qu'une colonne de `livre` : les recherches de livres
    ne chargent jamais les images, seule la route qui renvoie la couverture les lit.
    """

    __tablename__ = "couverture"

    # Clé primaire = clé étrangère : un livre a au plus une couverture.
    # ON DELETE CASCADE : supprimer le livre supprime sa couverture.
    livre_id: Mapped[int] = mapped_column(ForeignKey("livre.id", ondelete="CASCADE"), primary_key=True)
    contenu: Mapped[bytes] = mapped_column(LargeBinary)  # BLOB dans Oracle
    type_mime: Mapped[str] = mapped_column(String(20))
    taille: Mapped[int] = mapped_column(Integer)
    date_maj: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )
