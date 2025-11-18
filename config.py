import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev")
    SQLITE_DB_PATH = BASE_DIR / "banco_dados" / "tronik.db"
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{SQLITE_DB_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevConfig(BaseConfig):
    DEBUG = True
