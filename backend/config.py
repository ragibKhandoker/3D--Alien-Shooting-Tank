import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Neon -> Dashboard -> Connect -> connection string
DATABASE_URL = os.getenv("DATABASE_URL", "")
SCHEMA_FILE = (BASE_DIR / "../database/schema.sql").resolve()

# Signs login tokens. Without a fixed value everyone is logged out on every restart.
SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)

FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))

GAME_DIR = (BASE_DIR / os.getenv("GAME_DIR", "../First Program")).resolve()
GAME_FILE = os.getenv("GAME_FILE", "project.py")

FRONTEND_DIR = (BASE_DIR / "../frontend").resolve()
