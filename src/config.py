from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class _DatabaseSettings(BaseSettings):
    """Paramètres de connexion communs à l'API et aux migrations."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Chaque classe ne lit que ses propres variables et ignore les autres
        # (ex. l'API ne charge jamais ORACLE_PASSWORD ni APP_USER_PASSWORD)
        extra="ignore",
    )

    # Propriétaire du schéma : son nom sert aussi de nom de schéma
    app_user: str
    db_host: str = "127.0.0.1"
    db_port: int = 1521
    db_service: str = "FREEPDB1"

    @property
    def db_schema(self) -> str:
        """Schéma contenant les tables (celui du propriétaire)."""
        return self.app_user.upper()

    def _url(self, user: str, password: SecretStr) -> URL:
        # URL.create échappe les caractères spéciaux du mot de passe
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

    # --- Sécurité (JWT) ---
    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

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
    return Settings()  # type: ignore[call-arg]
