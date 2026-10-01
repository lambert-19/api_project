from logging.config import fileConfig

from sqlalchemy import Connection, create_engine, pool, text

from alembic import context

import models  # noqa: F401  (enregistre toutes les tables dans Base.metadata)
from config import MigrationSettings
from models.base import Base

# Rôle créé par docker/oracle/initdb/01-securite.sh, attribué à l'utilisateur de l'API
ROLE_API = "BIBLIO_API_ROLE"

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Les migrations s'exécutent avec le propriétaire du schéma (BIBLIO)
settings = MigrationSettings()  # type: ignore[call-arg]

# Index sur expression (CASE ...) : Alembic ne sait pas les comparer avec la base
# et proposerait de les supprimer/recréer à chaque --autogenerate
INDEX_FONCTIONNELS = {"uq_emprunt_livre_en_cours"}


def include_object(objet, nom, type_, reflected, compare_to) -> bool:
    """Ignore la comparaison d'un index fonctionnel déjà présent en base et dans les modèles."""
    if type_ == "index" and nom in INDEX_FONCTIONNELS and compare_to is not None:
        return False
    return True


def accorder_droits_api(connection: Connection) -> None:
    """Donne à l'API les droits de lecture/écriture sur toutes les tables du schéma.

    Rejoué après chaque migration : les nouvelles tables sont couvertes
    automatiquement, sans GRANT à écrire dans chaque fichier de migration.
    """
    tables = connection.execute(
        text(
            "SELECT table_name FROM user_tables "
            "WHERE dropped = 'NO' AND table_name <> 'ALEMBIC_VERSION'"
        )
    ).scalars()
    for table in tables:
        connection.execute(
            text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON "{table}" TO {ROLE_API}')
        )


def run_migrations_offline() -> None:
    """Mode offline (`alembic upgrade head --sql`) : génère le SQL sans l'exécuter.

    Les GRANT ne sont pas inclus dans ce mode.
    """
    context.configure(
        url=settings.migration_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Mode normal : se connecte à Oracle et applique les migrations."""
    connectable = create_engine(settings.migration_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()

        accorder_droits_api(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
