"""Crée un administrateur, ou promeut un utilisateur existant.

Usage, depuis la racine du projet : uv run python src/creer_admin.py
"""

from getpass import getpass

from sqlalchemy import select

from database import SessionLocal
from models import RoleUtilisateur, Utilisateur
from schemas.utilisateur import UtilisateurCreate
from security import hasher_mot_de_passe


def main() -> None:
    email = input("Email : ").strip().lower()
    with SessionLocal() as db:
        utilisateur = db.scalar(select(Utilisateur).where(Utilisateur.email == email))
        if utilisateur:
            utilisateur.role = RoleUtilisateur.ADMIN
            print(f"{email} est maintenant administrateur.")
        else:
            donnees = UtilisateurCreate(
                nom=input("Nom : "),
                email=email,
                mot_de_passe=getpass("Mot de passe (8 caractères minimum) : "),
            )
            db.add(
                Utilisateur(
                    nom=donnees.nom,
                    email=donnees.email,
                    mot_de_passe_hash=hasher_mot_de_passe(donnees.mot_de_passe),
                    role=RoleUtilisateur.ADMIN,
                )
            )
            print(f"Administrateur {email} créé.")
        db.commit()


if __name__ == "__main__":
    main()
