from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import get_db
from routers import auth, emprunts, livres, utilisateurs

app = FastAPI(
    title="API Bibliothèque",
    description="Gestion d'une bibliothèque en ligne : utilisateurs, livres et emprunts.",
    version="0.1.0",
)

app.include_router(auth.router)
app.include_router(utilisateurs.router)
app.include_router(livres.router)
app.include_router(emprunts.router)


@app.get("/health", tags=["Système"])
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    """Vérifie que l'API répond et que la base Oracle est joignable (utilisé par le healthcheck Docker)."""
    try:
        db.execute(text("SELECT 1 FROM dual"))
    except SQLAlchemyError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Base de données injoignable")
    return {"status": "ok", "database": "ok"}
