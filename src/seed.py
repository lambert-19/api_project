"""Remplit la base avec des données de démonstration.

Usage, depuis la racine du projet : uv run python src/seed.py
Refuse de s'exécuter si la base contient déjà des livres.
"""

from datetime import date, datetime, timedelta

from sqlalchemy import func, select

from database import SessionLocal
from models import Emprunt, Livre, RoleUtilisateur, Utilisateur
from security import hasher_mot_de_passe

MOT_DE_PASSE = "demo1234"

UTILISATEURS = [
    ("Admin Bibliothèque", "admin@demo.fr", None, RoleUtilisateur.ADMIN),
    ("Saer", "saer@demo.fr", "+33 6 12 34 56 78", RoleUtilisateur.MEMBRE),
    ("Ibrahim", "ibrahim@demo.fr", "06 98 76 54 32", RoleUtilisateur.MEMBRE),
]

LIVRES = [
    ("Dune", "Frank Herbert", "Science-fiction", date(1965, 8, 1), "9782266320481"),
    ("Fondation", "Isaac Asimov", "Science-fiction", date(1951, 5, 1), "9782070360536"),
    ("1984", "George Orwell", "Science-fiction", date(1949, 6, 8), "9782070368228"),
    ("Les Misérables", "Victor Hugo", "Roman", date(1862, 4, 3), "9782253096337"),
    ("Notre-Dame de Paris", "Victor Hugo", "Roman", date(1831, 3, 16), "9782253009689"),
    ("L'Étranger", "Albert Camus", "Roman", date(1942, 5, 19), "9782070360024"),
    ("Le Petit Prince", "Antoine de Saint-Exupéry", "Jeunesse", date(1943, 4, 6), "9782070612758"),
    ("Harry Potter à l'école des sorciers", "J. K. Rowling", "Jeunesse", date(1997, 6, 26), "9782070584628"),
    ("Le Comte de Monte-Cristo", "Alexandre Dumas", "Aventure", date(1844, 8, 28), "9782253098058"),
    ("Vingt mille lieues sous les mers", "Jules Verne", "Aventure", date(1870, 6, 20), "9782253006329"),
    ("Sapiens", "Yuval Noah Harari", "Essai", date(2011, 1, 1), "9782226257017"),
    ("Le Deuxième Sexe", "Simone de Beauvoir", "Essai", date(1949, 6, 1), "9782070323517"),
]


def main() -> None:
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Livre)):
            print("La base contient déjà des livres : seed annulé.")
            return

        utilisateurs = {
            email: Utilisateur(
                nom=nom,
                email=email,
                telephone=telephone,
                mot_de_passe_hash=hasher_mot_de_passe(MOT_DE_PASSE),
                role=role,
            )
            for nom, email, telephone, role in UTILISATEURS
        }
        livres = {
            titre: Livre(titre=titre, auteur=auteur, genre=genre, date_publication=publication, isbn=isbn)
            for titre, auteur, genre, publication, isbn in LIVRES
        }
        db.add_all([*utilisateurs.values(), *livres.values()])

        aujourdhui = date.today()
        maintenant = datetime.now().replace(microsecond=0)
        saer, ibrahim = utilisateurs["saer@demo.fr"], utilisateurs["ibrahim@demo.fr"]
        db.add_all(
            [
                Emprunt(utilisateur=saer, livre=livres["Dune"], date_retour_prevue=aujourdhui + timedelta(days=10)),
                Emprunt(
                    utilisateur=saer,
                    livre=livres["Les Misérables"],
                    date_emprunt=maintenant - timedelta(days=40),
                    date_retour_prevue=aujourdhui - timedelta(days=26),
                    date_retour=maintenant - timedelta(days=30),
                ),
                Emprunt(
                    utilisateur=ibrahim,
                    livre=livres["1984"],
                    date_emprunt=maintenant - timedelta(days=20),
                    date_retour_prevue=aujourdhui - timedelta(days=6),
                ),
            ]
        )
        livres["Dune"].disponible = False
        livres["1984"].disponible = False
        db.commit()

    print(f"{len(UTILISATEURS)} utilisateurs et {len(LIVRES)} livres créés (mot de passe : {MOT_DE_PASSE})")
    for nom, email, _, role in UTILISATEURS:
        print(f"  {role.value:<6}  {email:<17}  {nom}")
    print("Emprunts : Saer a « Dune » en cours et a rendu « Les Misérables » ; Ibrahim est en retard pour « 1984 ».")


if __name__ == "__main__":
    main()
