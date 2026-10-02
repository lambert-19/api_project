"""Middleware 413 : refuse les corps de requête trop volumineux.

Protège l'API contre l'envoi de données énormes (saturation de la mémoire).
Deux vérifications :
1. l'en-tête Content-Length annonce une taille trop grande -> refus immédiat, sans rien lire ;
2. pas d'en-tête (envoi « chunked ») -> on compte les octets au fil de la lecture.
"""

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class LimiteTailleRequete:
    def __init__(self, app: ASGIApp, taille_max: int) -> None:
        self.app = app
        self.taille_max = taille_max
        self.message = f"Corps de la requête trop volumineux (maximum {taille_max // 1024} Ko)"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        longueur = dict(scope["headers"]).get(b"content-length", b"")
        if longueur.isdigit() and int(longueur) > self.taille_max:
            reponse = JSONResponse({"detail": self.message}, status.HTTP_413_CONTENT_TOO_LARGE)
            await reponse(scope, receive, send)
            return

        octets_recus = 0

        async def receive_limite() -> Message:
            nonlocal octets_recus
            message = await receive()
            if message["type"] == "http.request":
                octets_recus += len(message.get("body", b""))
                if octets_recus > self.taille_max:
                    # FastAPI relaie les HTTPException levées pendant la lecture du corps
                    raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, self.message)
            return message

        await self.app(scope, receive_limite, send)
