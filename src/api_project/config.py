from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    """Configuration de l'application, lue depuis les variables d'environnement et le fichier .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # .env contient aussi ORACLE_PASSWORD (admin, réservé à Docker) : l'API l'ignore
        extra="ignore",
    )

    # --- Base de données (utilisateur applicatif, droits limités) ---
    app_user: str
    app_user_password: SecretStr
    db_host: str = "127.0.0.1"
    db_port: int = 1521
    db_service: str = "FREEPDB1"

    # --- Sécurité (JWT) ---
    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    @property
    def database_url(self) -> URL:
        # URL.create échappe les caractères spéciaux du mot de passe
        return URL.create(
            "oracle+oracledb",
            username=self.app_user,
            password=self.app_user_password.get_secret_value(),
            host=self.db_host,
            port=self.db_port,
            query={"service_name": self.db_service},
        )


@lru_cache
def get_settings() -> Settings:
    """Settings chargés une seule fois ; utilisable comme dépendance FastAPI (Depends(get_settings))."""
    return Settings()  # type: ignore[call-arg]
