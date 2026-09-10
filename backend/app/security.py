"""Segurança: cifra do PAT em repouso (Fernet) e JWT de sessão (HS256)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.fernet import Fernet, InvalidToken

from backend.app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _load_fernet() -> Fernet:
    key = settings.pat_encryption_key.strip()
    if key:
        return Fernet(key.encode())
    # Dev/CI sem chave: gera uma efêmera. PATs salvos não sobrevivem a restart.
    logger.warning(
        "PAT_ENCRYPTION_KEY não definida — usando chave efêmera; "
        "PATs salvos serão perdidos ao reiniciar o processo."
    )
    return Fernet(Fernet.generate_key())


_fernet = _load_fernet()


def encrypt_pat(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_pat(ciphertext: str) -> str:
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError(
            "Não foi possível decifrar o PAT armazenado. Se a chave de cifra "
            "mudou, o usuário precisa salvar o PAT novamente no perfil."
        ) from exc


# --- Sessão (JWT em cookie httponly) ---

_ALG = "HS256"


def issue_session(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(hours=settings.session_ttl_hours)).timestamp()
        ),
    }
    return jwt.encode(payload, settings.session_secret, algorithm=_ALG)


def read_session(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.session_secret, algorithms=[_ALG])
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None
