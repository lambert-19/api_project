"""Modèles SQLAlchemy.

Chaque modèle doit être importé ici : Alembic importe ce package pour
connaître toutes les tables (autogenerate).
"""

from models.base import Base

__all__ = ["Base"]
