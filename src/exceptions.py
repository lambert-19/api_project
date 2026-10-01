"""Erreurs métier : levées par les services, converties en réponses HTTP dans main.py."""

from fastapi import status


class ErreurMetier(Exception):
    statut = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class Introuvable(ErreurMetier):
    statut = status.HTTP_404_NOT_FOUND


class Interdit(ErreurMetier):
    statut = status.HTTP_403_FORBIDDEN


class Conflit(ErreurMetier):
    statut = status.HTTP_409_CONFLICT
