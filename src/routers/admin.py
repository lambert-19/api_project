"""Routes d'administration : /v1/admin/...

📖 Doc FastAPI : Bigger Applications → dépendances au niveau d'un APIRouter, include_router

La protection est déclarée au niveau des routeurs, pas dans chaque route :
- ce routeur /admin exige le rôle administrateur pour TOUTES ses routes ;
- chaque sous-routeur exige en plus sa permission (livres:ecrire ou emprunts:gerer).
Une route ajoutée plus tard dans ces routeurs est donc protégée automatiquement :
impossible d'oublier la vérification.
"""

from fastapi import APIRouter, Depends

from dependances import exiger_role_admin
from routers import emprunts, livres

router = APIRouter(prefix="/admin", tags=["Administration"], dependencies=[Depends(exiger_role_admin)])

router.include_router(livres.router_admin)  # /admin/books
router.include_router(emprunts.router_admin)  # /admin/loans
