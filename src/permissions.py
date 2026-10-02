"""Permissions (scopes OAuth2) : ce qu'un jeton JWT autorise à faire.

📖 Doc FastAPI : Advanced User Guide → Advanced Security → OAuth2 scopes

Chaque route protégée déclare la permission dont elle a besoin. À la connexion,
l'utilisateur reçoit les permissions de son rôle (ou seulement celles qu'il demande).
"""

from models import RoleUtilisateur

SCOPES = {
    "profil": "Lire son profil, ses emprunts en cours et son historique",
    "emprunts": "Emprunter et rendre ses livres",
    "livres:ecrire": "Ajouter, modifier et supprimer des livres (administrateurs)",
    "emprunts:gerer": "Voir les retards, enregistrer le retour de n'importe quel emprunt (administrateurs)",
}

SCOPES_PAR_ROLE: dict[RoleUtilisateur, frozenset[str]] = {
    RoleUtilisateur.MEMBRE: frozenset({"profil", "emprunts"}),
    RoleUtilisateur.ADMIN: frozenset(SCOPES),
}


def scopes_autorises(role: RoleUtilisateur) -> frozenset[str]:
    return SCOPES_PAR_ROLE[role]
