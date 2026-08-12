import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'mayajal.db'}")
AUTH_MODE = os.getenv("AUTH_MODE", "dev").lower()
ENTRA_TENANT_ID = os.getenv("ENTRA_TENANT_ID", "")
ENTRA_CLIENT_ID = os.getenv("ENTRA_CLIENT_ID", "")
ENTRA_AUDIENCE = os.getenv("ENTRA_AUDIENCE", ENTRA_CLIENT_ID)
ASSETS_DIR = PROJECT_DIR / "assets"
DETECTION_PACKS_DIR = ASSETS_DIR / "detection-packs"
RUNTIME_DIR = BASE_DIR / "runtime"
DETECTION_BUNDLES_DIR = RUNTIME_DIR / "detection-bundles"
DETECTION_BUNDLES_DIR.mkdir(parents=True, exist_ok=True)
LAB_RUNTIME_DIR = RUNTIME_DIR / "labs"
LAB_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
IMPORTED_MACHINES_DIR = RUNTIME_DIR / "imported-machines"
IMPORTED_MACHINES_DIR.mkdir(parents=True, exist_ok=True)
MAYAJAL_MASTER_URL = os.getenv("MAYAJAL_MASTER_URL", "")
MAYAJAL_TELEMETRY_HOST = os.getenv("MAYAJAL_TELEMETRY_HOST", "host.docker.internal")
MAYAJAL_TELEMETRY_PORT = os.getenv("MAYAJAL_TELEMETRY_PORT", "24224")
MAYAJAL_OPENSEARCH_URL = os.getenv("MAYAJAL_OPENSEARCH_URL", "http://127.0.0.1:9200")
MAYAJAL_OPENSEARCH_INDEX = os.getenv("MAYAJAL_OPENSEARCH_INDEX", "mayajal-logs-*")
MAYAJAL_DETECTION_ENGINE_MODE = os.getenv("MAYAJAL_DETECTION_ENGINE_MODE", "legacy").lower()
if MAYAJAL_DETECTION_ENGINE_MODE not in {"legacy", "shadow", "packs"}:
    raise RuntimeError("MAYAJAL_DETECTION_ENGINE_MODE must be legacy, shadow, or packs.")
MAYAJAL_CORS_ORIGINS = [origin.strip() for origin in os.getenv("MAYAJAL_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if origin.strip()]
MAYAJAL_CORS_ORIGIN_REGEX = os.getenv("MAYAJAL_CORS_ORIGIN_REGEX", r"^http://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+|192\.168\.\d+\.\d+)(:\d+)?$")
MAYAJAL_SESSION_MAX_MINUTES = max(5, int(os.getenv("MAYAJAL_SESSION_MAX_MINUTES", "120")))
MAYAJAL_MIN_FREE_DISK_GB = max(0.1, float(os.getenv("MAYAJAL_MIN_FREE_DISK_GB", "2")))
MAYAJAL_MIN_AVAILABLE_MEMORY_MB = max(64, int(os.getenv("MAYAJAL_MIN_AVAILABLE_MEMORY_MB", "512")))


def require_entra_config() -> None:
    if not ENTRA_TENANT_ID or not ENTRA_CLIENT_ID:
        raise RuntimeError("ENTRA_TENANT_ID and ENTRA_CLIENT_ID are required when AUTH_MODE=entra.")
