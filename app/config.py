import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "nourish-dev-secret-key-change-in-prod")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "nourish-admin")
    DATABASE_PATH = os.environ.get("DATABASE_PATH", str(BASE_DIR / "nourish.db"))
    GOOGLE_SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "")
    # Conda environments set HOST="x86_64-conda-linux-gnu" which breaks hostname binding.
    # We prioritize NOURISH_HOST, FLASK_RUN_HOST, or fallback to 0.0.0.0 if HOST is a toolchain triplet.
    raw_host = os.environ.get("NOURISH_HOST") or os.environ.get("FLASK_RUN_HOST")
    if not raw_host:
        candidate = os.environ.get("HOST", "")
        if candidate and "linux-gnu" not in candidate and "conda" not in candidate:
            raw_host = candidate
        else:
            raw_host = "0.0.0.0"
    HOST = raw_host
    PORT = int(os.environ.get("NOURISH_PORT") or os.environ.get("PORT", 8002))
