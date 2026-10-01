"""Test de charge : débit (requêtes/s et /min) et temps de réponse, route par route.

1. Lancer l'API en mode production : uv run fastapi run src/main.py [--workers 4]
2. Dans un autre terminal       : uv run python scripts/charge.py [--duree 10] [--concurrence 20]

Le script crée ses propres utilisateurs et livres, puis les supprime à la fin.
"""

import argparse
import asyncio
import statistics
import sys
import time
from collections import Counter
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx
from sqlalchemy import delete, select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from database import SessionLocal  # noqa: E402
from models import Emprunt, Livre, Utilisateur  # noqa: E402
from security import hasher_mot_de_passe  # noqa: E402

PREFIXE = "charge-"
MOT_DE_PASSE = "motdepasse-charge"

Requete = Callable[[httpx.AsyncClient, int], Awaitable[list[httpx.Response]]]


def preparer(nb_workers: int) -> tuple[list[str], list[int]]:
    hash_ = hasher_mot_de_passe(MOT_DE_PASSE)
    with SessionLocal() as db:
        utilisateurs = [
            Utilisateur(nom=f"{PREFIXE}{i}", email=f"{PREFIXE}{i}@test.example", mot_de_passe_hash=hash_)
            for i in range(nb_workers)
        ]
        livres = [Livre(titre=f"{PREFIXE}livre {i}", auteur=f"{PREFIXE}auteur") for i in range(nb_workers)]
        db.add_all([*utilisateurs, *livres])
        db.commit()
        return [u.email for u in utilisateurs], [livre.id for livre in livres]


def nettoyer() -> None:
    with SessionLocal() as db:
        livres = select(Livre.id).where(Livre.titre.like(f"{PREFIXE}%"))
        db.execute(delete(Emprunt).where(Emprunt.livre_id.in_(livres)))
        db.execute(delete(Livre).where(Livre.titre.like(f"{PREFIXE}%")))
        db.execute(delete(Utilisateur).where(Utilisateur.email.like(f"{PREFIXE}%")))
        db.commit()


async def mesurer(nom: str, requete: Requete, url: str, duree: float, concurrence: int) -> dict:
    latences: list[float] = []
    codes: Counter[int] = Counter()
    fin = time.perf_counter() + duree

    async def worker(i: int) -> None:
        async with httpx.AsyncClient(base_url=url, timeout=30) as client:
            while time.perf_counter() < fin:
                debut = time.perf_counter()
                reponses = await requete(client, i)
                ecoule = (time.perf_counter() - debut) / len(reponses)
                for reponse in reponses:
                    latences.append(ecoule)
                    codes[reponse.status_code] += 1

    debut = time.perf_counter()
    await asyncio.gather(*(worker(i) for i in range(concurrence)))
    total = time.perf_counter() - debut
    quantiles = statistics.quantiles(latences, n=100) if len(latences) > 1 else [latences[0]] * 99
    return {
        "nom": nom,
        "requetes": len(latences),
        "par_seconde": len(latences) / total,
        "p50": quantiles[49] * 1000,
        "p95": quantiles[94] * 1000,
        "p99": quantiles[98] * 1000,
        "erreurs": sum(n for code, n in codes.items() if code >= 400),
        "codes": dict(codes),
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--duree", type=float, default=10, help="secondes par scénario")
    parser.add_argument("--concurrence", type=int, default=20, help="clients simultanés")
    args = parser.parse_args()

    async with httpx.AsyncClient(base_url=args.url) as client:
        if (await client.get("/health")).status_code != 200:
            sys.exit(f"L'API ne répond pas sur {args.url}")

    nettoyer()
    emails, livres = preparer(args.concurrence)
    try:
        jetons = []
        async with httpx.AsyncClient(base_url=args.url) as client:
            for email in emails:
                reponse = await client.post("/auth/token", data={"username": email, "password": MOT_DE_PASSE})
                jetons.append({"Authorization": f"Bearer {reponse.json()['access_token']}"})

        async def emprunt_retour(c: httpx.AsyncClient, i: int) -> list[httpx.Response]:
            emprunt = await c.post("/loans", json={"livre_id": livres[i]}, headers=jetons[i])
            retour = await c.post(f"/loans/{emprunt.json()['id']}/return", headers=jetons[i])
            return [emprunt, retour]

        scenarios: list[tuple[str, Requete]] = [
            ("GET /health", lambda c, i: asyncio.gather(c.get("/health"))),
            ("GET /books (recherche)", lambda c, i: asyncio.gather(c.get("/books", params={"author": PREFIXE}))),
            ("GET /books/{id}", lambda c, i: asyncio.gather(c.get(f"/books/{livres[i]}"))),
            ("GET /users/me (JWT)", lambda c, i: asyncio.gather(c.get("/users/me", headers=jetons[i]))),
            (
                "POST /auth/token (Argon2)",
                lambda c, i: asyncio.gather(
                    c.post("/auth/token", data={"username": emails[i], "password": MOT_DE_PASSE})
                ),
            ),
            ("POST /loans + /return", emprunt_retour),
        ]

        print(f"{args.concurrence} clients simultanés, {args.duree:g} s par scénario, sur {args.url}\n")
        print(f"{'Scénario':<28}{'req/s':>8}{'req/min':>10}{'p50 ms':>9}{'p95 ms':>9}{'p99 ms':>9}{'erreurs':>9}")
        for nom, requete in scenarios:
            r = await mesurer(nom, requete, args.url, args.duree, args.concurrence)
            print(
                f"{r['nom']:<28}{r['par_seconde']:>8.0f}{r['par_seconde'] * 60:>10.0f}"
                f"{r['p50']:>9.1f}{r['p95']:>9.1f}{r['p99']:>9.1f}{r['erreurs']:>9}"
            )
            if r["erreurs"]:
                print(f"{'':<28}codes : {r['codes']}")
    finally:
        nettoyer()


if __name__ == "__main__":
    asyncio.run(main())
