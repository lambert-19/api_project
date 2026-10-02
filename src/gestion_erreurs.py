"""Réponses d'erreur en français et documentation Swagger des codes communs.

- 404 / 405 / 401 générés par FastAPI lui-même (route inexistante, mauvaise méthode,
  jeton absent) : message traduit en français.
- 422 : un message lisible par champ, au lieu du format technique de Pydantic.
- Swagger : le schéma 422 est remplacé, et 413 / 500 / 503 sont ajoutés aux routes.
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from reponses import erreur
from schemas.erreur import Erreur, ErreurValidation

# Messages par défaut de Starlette / FastAPI -> message en français
TRADUCTIONS = {
    "Not Found": "Route introuvable : vérifier l'URL",
    "Not authenticated": "Authentification requise : envoyer un jeton dans l'en-tête Authorization",
}


async def erreur_http(request: Request, exc: StarletteHTTPException) -> Response:
    """Traduit les erreurs générées par le framework ; les autres sont renvoyées telles quelles."""
    if exc.status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
        autorisees = (exc.headers or {}).get("Allow", "")
        return JSONResponse(
            {"detail": f"Méthode {request.method} non autorisée sur cette route (autorisées : {autorisees})"},
            status_code=exc.status_code,
            headers=exc.headers,
        )
    if exc.detail in TRADUCTIONS:
        exc = StarletteHTTPException(exc.status_code, TRADUCTIONS[exc.detail], exc.headers)
    return await http_exception_handler(request, exc)


def _message_validation(err: dict[str, Any]) -> str:
    """Message en français pour une erreur Pydantic (err["type"] identifie le problème)."""
    ctx = err.get("ctx", {})
    match err["type"]:
        case "missing":
            return "Champ obligatoire"
        case "string_too_short":
            return f"Au moins {ctx['min_length']} caractère(s)"
        case "string_too_long":
            return f"Au plus {ctx['max_length']} caractères"
        case "string_pattern_mismatch":
            return "Format invalide"
        case "string_type":
            return "Doit être une chaîne de caractères"
        case "greater_than_equal":
            return f"Doit être supérieur ou égal à {ctx['ge']}"
        case "less_than_equal":
            return f"Doit être inférieur ou égal à {ctx['le']}"
        case "greater_than":
            return f"Doit être supérieur à {ctx['gt']}"
        case "less_than":
            return f"Doit être inférieur à {ctx['lt']}"
        case "int_parsing" | "int_type" | "int_from_float":
            return "Doit être un nombre entier"
        case "bool_parsing" | "bool_type":
            return "Doit être true ou false"
        case "date_parsing" | "date_type" | "date_from_datetime_parsing" | "date_from_datetime_inexact":
            return "Date invalide (format attendu : AAAA-MM-JJ)"
        case "enum":
            return f"Valeur non autorisée (attendu : {ctx.get('expected', '')})"
        case "json_invalid":
            return "JSON invalide"
        case "model_attributes_type" | "dict_type" | "model_type":
            return "Objet JSON attendu"
        case "value_error":
            message = err["msg"].removeprefix("Value error, ")
            return "Adresse email invalide" if "email address" in message else message
        case _:
            return err["msg"]


async def erreur_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
    """422 : un message lisible par champ invalide."""
    erreurs = []
    for err in exc.errors():
        emplacement, *chemin = err["loc"]
        erreurs.append(
            {
                "emplacement": str(emplacement),
                "champ": ".".join(str(partie) for partie in chemin) or None,
                "message": _message_validation(err),
            }
        )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": "Données invalides", "erreurs": erreurs},
    )


def personnaliser_openapi(app: FastAPI, taille_max_requete: int) -> None:
    """Complète le schéma OpenAPI généré par FastAPI (affiché dans /docs)."""
    generer_par_defaut = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema
        schema = generer_par_defaut()
        composants = schema.setdefault("components", {}).setdefault("schemas", {})
        composants.setdefault("Erreur", Erreur.model_json_schema())

        # Schéma de la réponse 422 personnalisée (et de ses sous-modèles)
        schema_422 = ErreurValidation.model_json_schema(ref_template="#/components/schemas/{model}")
        composants.update(schema_422.pop("$defs", {}))
        composants["ErreurValidation"] = schema_422
        for inutile in ("HTTPValidationError", "ValidationError"):
            composants.pop(inutile, None)

        reponse_422 = {
            "description": "Données invalides (détail par champ)",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErreurValidation"}}},
        }
        reponses_communes = {
            "500": _vers_openapi(erreur("Erreur interne inattendue", "Erreur interne")),
            "503": _vers_openapi(
                erreur("Base de données momentanément indisponible", "Base de données momentanément indisponible")
            ),
        }
        reponse_413 = _vers_openapi(
            erreur(
                "Corps de la requête trop volumineux",
                f"Corps de la requête trop volumineux (maximum {taille_max_requete // 1024} Ko)",
            )
        )

        for operations in schema.get("paths", {}).values():
            for operation in operations.values():
                reponses = operation.setdefault("responses", {})
                if "422" in reponses:
                    reponses["422"] = reponse_422
                if "requestBody" in operation:
                    reponses.setdefault("413", reponse_413)
                for code, reponse in reponses_communes.items():
                    reponses.setdefault(code, reponse)

        app.openapi_schema = schema
        return schema

    app.openapi = openapi  # type: ignore[method-assign]


def _vers_openapi(reponse: dict[str, Any]) -> dict[str, Any]:
    """Convertit une réponse `erreur()` (avec model=Erreur) au format OpenAPI brut."""
    contenu = reponse.get("content", {}).get("application/json", {})
    return {
        "description": reponse["description"],
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Erreur"}, **contenu}},
    }
