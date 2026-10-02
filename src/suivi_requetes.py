"""Middleware HTTP de suivi : identifiant unique et durée de chaque requête.

📖 Doc FastAPI : Middleware (exemple de l'en-tête X-Process-Time)

- `X-Request-ID` : identifiant de la requête, renvoyé au client et repris dans les
  journaux. Si un utilisateur signale une erreur, cet identifiant permet de retrouver
  la ligne correspondante dans les journaux du serveur.
  Si le client (ou un proxy) en envoie déjà un valide, il est conservé.
- `X-Process-Time` : temps de traitement côté serveur, en secondes.
- Les requêtes lentes sont signalées dans les journaux.
"""

import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

logger = logging.getLogger("uvicorn.error")

SEUIL_REQUETE_LENTE = 1.0  # secondes
# Identifiant fourni par le client : accepté seulement s'il est court et sans caractères
# spéciaux (il est recopié dans les journaux et dans un en-tête de réponse)
FORMAT_ID_CLIENT = re.compile(r"[A-Za-z0-9._-]{1,64}")


async def suivre_requete(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    id_client = request.headers.get("X-Request-ID", "")
    request_id = id_client if FORMAT_ID_CLIENT.fullmatch(id_client) else uuid.uuid4().hex
    request.state.request_id = request_id

    debut = time.perf_counter()
    response = await call_next(request)
    duree = time.perf_counter() - debut

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{duree:.4f}"
    if duree > SEUIL_REQUETE_LENTE:
        logger.warning(
            "Requête lente (%.2f s) : %s %s -> %s [id=%s]",
            duree, request.method, request.url.path, response.status_code, request_id,
        )
    return response
