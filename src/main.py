import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from config import get_settings
from database import engine, get_db
from documentation import installer_documentation
from exceptions import ErreurMetier
from gestion_erreurs import erreur_http, erreur_validation, personnaliser_openapi
from limite_taille import LimiteTailleRequete
from reponses import erreur
from routers import auth, emprunts, livres, utilisateurs
from suivi_requetes import suivre_requete

logger = logging.getLogger("uvicorn.error")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Au démarrage : refuse de démarrer si Oracle est injoignable. À l'arrêt : ferme les connexions."""
    try:
        with engine.connect() as connexion:
            connexion.execute(text("SELECT 1 FROM dual"))
    except SQLAlchemyError:
        logger.critical("Base Oracle injoignable au démarrage (%s:%s)", settings.db_host, settings.db_port)
        raise
    logger.info("Connexion à Oracle vérifiée (%s)", settings.api_user.upper())
    yield
    engine.dispose()


DESCRIPTION = """
Gestion d'une bibliothèque en ligne : utilisateurs, livres et emprunts.
**S'authentifier :** créer un compte avec `POST /users/register`, puis cliquer sur
**Authorize** et se connecter avec son email et son mot de passe.

**Permissions (scopes OAuth2) :** chaque route protégée exige une permission, indiquée par
le cadenas. Un membre reçoit `profil` et `emprunts` ; un administrateur reçoit en plus
`livres:ecrire` et `emprunts:gerer`. Sans case cochée dans **Authorize**, le jeton reçoit
toutes les permissions du rôle.

**Suivi :** chaque réponse contient `X-Request-ID` (à communiquer en cas de problème,
il est repris dans les journaux du serveur) et `X-Process-Time` (durée de traitement, en secondes).

**Codes de réponse :** <span>2xx succès</span> · <span>4xx erreur dans la requête</span> ·
<span>5xx erreur du serveur</span>
"""
# ↑ Doit rester le dernier paragraphe : src/static/swagger.css colore ces 3 <span> par leur position
# (Swagger retire les attributs class et style de la description)

TAGS = [
    {"name": "Authentification", "description": "Connexion et obtention d'un jeton JWT."},
    {"name": "Utilisateurs", "description": "Inscription, profil, emprunts en cours et historique."},
    {"name": "Livres", "description": "Recherche et consultation pour tous ; gestion de l'inventaire pour les administrateurs."},
    {"name": "Emprunts", "description": "Emprunt et retour des livres, suivi des retards."},
    {"name": "Système", "description": "Supervision de l'API."},
]

app = FastAPI(
    title="API Bibliothèque",
    description=DESCRIPTION,
    version="1.0.0",
    openapi_tags=TAGS,
    lifespan=lifespan,
    docs_url=None,  # remplacée par installer_documentation (codes de réponse colorés)
)
installer_documentation(app)

# Le dernier ajouté est le plus externe : CORS -> suivi -> limite de taille -> routes.
# Ainsi les réponses 413 ont aussi un X-Request-ID et leurs en-têtes CORS.
app.add_middleware(LimiteTailleRequete, taille_max=settings.taille_max_requete)
app.add_middleware(BaseHTTPMiddleware, dispatch=suivre_requete)  # équivaut à @app.middleware("http")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    # En-têtes de réponse lisibles par le JavaScript d'un site autorisé
    expose_headers=["X-Request-ID", "X-Process-Time", "Location", "Retry-After"],
)


app.add_exception_handler(StarletteHTTPException, erreur_http)  # 404 / 405 / 401 en français
app.add_exception_handler(RequestValidationError, erreur_validation)  # 422 lisible
personnaliser_openapi(app, settings.taille_max_requete)


@app.exception_handler(ErreurMetier)
async def erreur_metier(_: Request, exc: ErreurMetier) -> JSONResponse:
    return JSONResponse(status_code=exc.statut, content={"detail": exc.message})


@app.exception_handler(SQLAlchemyError)
async def erreur_base(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Journalise l'erreur complète, mais ne renvoie jamais de détail SQL au client."""
    logger.exception(
        "Erreur base de données sur %s %s [id=%s]",
        request.method, request.url.path, getattr(request.state, "request_id", "-"),
    )
    if isinstance(exc, OperationalError | PoolTimeoutError) or (
        isinstance(exc, DBAPIError) and exc.connection_invalidated
    ):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Base de données momentanément indisponible"},
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Erreur interne"},
    )


app.include_router(auth.router)
app.include_router(utilisateurs.router)
app.include_router(livres.router)
app.include_router(emprunts.router)


@app.get(
    "/health",
    tags=["Système"],
    responses={503: erreur("Oracle ne répond pas", "Base de données injoignable")},
)
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    """Vérifie que l'API répond et que la base Oracle est joignable (utilisé par le healthcheck Docker)."""
    try:
        db.execute(text("SELECT 1 FROM dual"))
    except SQLAlchemyError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Base de données injoignable")
    return {"status": "ok", "database": "ok"}
