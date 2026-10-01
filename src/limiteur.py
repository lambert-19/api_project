"""Limite les échecs de connexion par adresse IP (protection contre la force brute)."""

import math
import time
from collections import defaultdict, deque
from threading import Lock


class LimiteurEchecs:
    """Au plus `max_echecs` échecs par clé sur une fenêtre glissante de `fenetre` secondes.

    En mémoire : chaque processus a son propre compteur, remis à zéro au redémarrage.
    """

    def __init__(self, max_echecs: int, fenetre: float) -> None:
        self.max_echecs = max_echecs
        self.fenetre = fenetre
        self._echecs: dict[str, deque[float]] = defaultdict(deque)
        self._verrou = Lock()

    def _purger(self, cle: str, maintenant: float) -> deque[float]:
        echecs = self._echecs[cle]
        while echecs and echecs[0] <= maintenant - self.fenetre:
            echecs.popleft()
        return echecs

    def attente(self, cle: str) -> int:
        """Secondes à attendre avant une nouvelle tentative (0 si autorisée)."""
        maintenant = time.monotonic()
        with self._verrou:
            echecs = self._purger(cle, maintenant)
            if len(echecs) < self.max_echecs:
                return 0
            return max(1, math.ceil(echecs[0] + self.fenetre - maintenant))

    def enregistrer_echec(self, cle: str) -> None:
        maintenant = time.monotonic()
        with self._verrou:
            self._purger(cle, maintenant).append(maintenant)

    def reinitialiser(self) -> None:
        with self._verrou:
            self._echecs.clear()


limiteur_connexion = LimiteurEchecs(max_echecs=5, fenetre=60)
