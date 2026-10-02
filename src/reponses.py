"""Codes d'erreur documentés dans Swagger (paramètre `responses=` des routes).

Les codes communs à toutes les routes (422, 413, 500, 503) sont ajoutés
automatiquement dans gestion_erreurs.personnaliser_openapi.
"""

from typing import Any

from schemas.erreur import Erreur


def erreur(description: str, *exemples: str) -> dict[str, Any]:
    """Réponse d'erreur pour Swagger, avec un ou plusieurs exemples de message."""
    reponse: dict[str, Any] = {"model": Erreur, "description": description}
    if len(exemples) == 1:
        reponse["content"] = {"application/json": {"example": {"detail": exemples[0]}}}
    elif exemples:
        reponse["content"] = {
            "application/json": {
                "examples": {
                    f"cas_{i}": {"summary": message, "value": {"detail": message}}
                    for i, message in enumerate(exemples, start=1)
                }
            }
        }
    return reponse


def creation(description: str) -> dict[int, dict[str, Any]]:
    """Réponse 201 avec l'en-tête Location (URL de la ressource créée)."""
    return {
        201: {
            "description": description,
            "headers": {
                "Location": {"description": "URL de la ressource créée", "schema": {"type": "string"}}
            },
        }
    }


NON_AUTHENTIFIE = {
    401: erreur(
        "Jeton absent, invalide ou expiré",
        "Authentification requise : envoyer un jeton dans l'en-tête Authorization",
        "Jeton invalide ou expiré",
    )
}

def permission_requise(scope: str) -> dict[int, dict[str, Any]]:
    """401 si pas authentifié, 403 si le jeton n'a pas la permission `scope`."""
    return {
        **NON_AUTHENTIFIE,
        403: erreur(f"Le jeton n'a pas la permission « {scope} »", f"Permission insuffisante : {scope} requis"),
    }

LIVRE_INTROUVABLE = {404: erreur("Aucun livre avec cet identifiant", "Livre introuvable")}
