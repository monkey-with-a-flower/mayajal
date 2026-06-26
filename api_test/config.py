import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'mayajal.db'}")
AUTH_MODE = os.getenv("AUTH_MODE", "dev").lower()
ENTRA_TENANT_ID = os.getenv("ENTRA_TENANT_ID", "")
ENTRA_CLIENT_ID = os.getenv("ENTRA_CLIENT_ID", "")
ENTRA_AUDIENCE = os.getenv("ENTRA_AUDIENCE", ENTRA_CLIENT_ID)


def require_entra_config() -> None:
    if not ENTRA_TENANT_ID or not ENTRA_CLIENT_ID:
        raise RuntimeError("ENTRA_TENANT_ID and ENTRA_CLIENT_ID are required when AUTH_MODE=entra.")
