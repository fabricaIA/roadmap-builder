"""Configuração da aplicação, carregada de variáveis de ambiente / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- GitHub OAuth (App de OAuth, só para login) ---
    github_oauth_client_id: str = ""
    github_oauth_client_secret: str = ""
    oauth_redirect_uri: str = "http://localhost:8000/api/auth/github/callback"
    # Escopos pedidos no login. Identidade só; org/role entram num PR posterior.
    oauth_scopes: str = "read:user user:email"

    # --- Sessão / segredos ---
    # JWT HS256 que assina o cookie de sessão.
    session_secret: str = "dev-insecure-session-secret-change-me"
    session_ttl_hours: int = 168  # 7 dias
    session_cookie_name: str = "rmb_session"
    oauth_state_cookie_name: str = "rmb_oauth_state"
    cookie_secure: bool = False  # True em produção (HTTPS)
    cookie_samesite: str = "lax"

    # Chave Fernet (urlsafe base64, 32 bytes) para cifrar o PAT em repouso.
    # Vazio => chave efêmera gerada no boot (PATs não sobrevivem a restart).
    pat_encryption_key: str = ""

    # --- Banco ---
    database_url: str = "sqlite:///./roadmap.db"

    # --- Front ---
    frontend_url: str = "http://localhost:5173"
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def oauth_configured(self) -> bool:
        return bool(self.github_oauth_client_id and self.github_oauth_client_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
