from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True, 
)

@event.listens_for(engine, "connect")
def _utiliser_schema_proprietaire(dbapi_connection, _connection_record) -> None:
    """Les tables appartiennent à BIBLIO : sans ça, BIBLIO_API devrait écrire BIBLIO.livre partout."""
    with dbapi_connection.cursor() as cursor:
        cursor.execute(f'ALTER SESSION SET CURRENT_SCHEMA = "{settings.db_schema}"')


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dépendance FastAPI : une session par requête, fermée même en cas d'erreur.

    Usage : `def route(db: Session = Depends(get_db))`
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
