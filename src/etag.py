"""ETag : empreinte du contenu d'une ressource, pour les requêtes conditionnelles.

📖 Doc FastAPI : Header Parameters, Response Headers, Return a Response Directly

- GET + `If-None-Match` : le client renvoie l'ETag de sa copie ; si le contenu n'a pas
  changé, réponse `304 Not Modified` sans corps (économise la bande passante).
- PATCH + `If-Match` : le client renvoie l'ETag de la version qu'il a lue ; si quelqu'un
  a modifié la ressource entre-temps, réponse `412 Precondition Failed` au lieu d'écraser
  sa modification (contrôle de concurrence optimiste).
"""

import hashlib

from pydantic import BaseModel


def etag_de(ressource: BaseModel) -> str:
    """ETag « fort » : empreinte SHA-256 de la représentation JSON renvoyée au client."""
    return '"' + hashlib.sha256(ressource.model_dump_json().encode()).hexdigest()[:20] + '"'


def correspond(entete: str | None, etag: str, *, comparaison_faible: bool) -> bool:
    """Vrai si l'en-tête (liste d'ETags séparés par des virgules, ou `*`) contient `etag`.

    If-None-Match utilise la comparaison faible (le préfixe `W/` est ignoré) ;
    If-Match exige la comparaison forte (un ETag `W/...` ne correspond jamais).
    """
    if entete is None:
        return False
    for valeur in (v.strip() for v in entete.split(",")):
        if valeur == "*":
            return True
        if comparaison_faible:
            valeur = valeur.removeprefix("W/")
        if valeur == etag:
            return True
    return False
