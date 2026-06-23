"""Centralised config — every env-tunable value lives here, nowhere else."""
import os

# Project root = directory containing this config/ package
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_DB = os.path.join(_PROJECT_ROOT, "db", "cinemaflo.db")


class Settings:
    DB_PATH: str = os.environ.get("CINEMAFLO_DB_PATH", _DEFAULT_DB)
    ADMIN_TOKEN: str = os.environ.get("CINEMAFLO_ADMIN_TOKEN", "admin-dev-token")
    MENU_CACHE_TTL_SECONDS: int = int(os.environ.get("CINEMAFLO_MENU_CACHE_TTL", "10"))
    CORS_ORIGINS: list[str] = ["*"]  # tightened in production


settings = Settings()
