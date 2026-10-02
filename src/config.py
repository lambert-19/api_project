from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

# Préfixe de toutes les routes de l'API : une future version incompatible serait servie
# sous /v2, sans casser les clients qui utilisent encore /v1
PREFIXE_API = "/v1"


class _DatabaseSettings(BaseSettings):
    """Paramètres de connexion communs à l'API et aux migrations."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    app_user: str
    db_host: str = "127.0.0.1"
    db_port: int = 1521
    db_service: str = "FREEPDB1"

    @property
    def db_schema(self) -> str:
        """Schéma contenant les tables (celui du propriétaire)."""
        return self.app_user.upper()

    def _url(self, user: str, password: SecretStr) -> URL:
        return URL.create(
            "oracle+oracledb",
            username=user,
            password=password.get_secret_value(),
            host=self.db_host,
            port=self.db_port,
            query={"service_name": self.db_service},
        )


class Settings(_DatabaseSettings):
    """Configuration de l'API. Ne contient PAS le mot de passe du propriétaire du schéma."""

    # Utilisateur de l'API : lecture/écriture des données seulement
    api_user: str
    api_user_password: SecretStr
    db_pool_size: int = 10

    # --- Sécurité (JWT) ---
    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Taille maximale d'un corps de requête, en octets (au-delà : 413)
    taille_max_requete: int = 1024 * 1024

    @property
    def database_url(self) -> URL:
        """Connexion de l'API (utilisateur à droits limités)."""
        return self._url(self.api_user, self.api_user_password)


class MigrationSettings(_DatabaseSettings):
    """Configuration d'Alembic : seul endroit où le mot de passe du propriétaire est lu."""

    app_user_password: SecretStr

    @property
    def migration_url(self) -> URL:
        """Connexion d'Alembic (propriétaire du schéma)."""
        return self._url(self.app_user, self.app_user_password)


@lru_cache
def get_settings() -> Settings:
    """Settings chargés une seule fois ; utilisable comme dépendance FastAPI (Depends(get_settings))."""
    return Settings() 
