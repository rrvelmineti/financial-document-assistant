"""Settings come from environment variables, so nothing secret is ever written into the code."""
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database_url: str
    data_dir: Path
    gemini_api_key: str
    gemini_model: str
    embedder: str           # "gemini" or "hashing"
    embedding_model: str
    max_upload_mb: int = 25
    max_pages: int = 600
    top_k: int = 6

    @property
    def ai_enabled(self):
        return bool(self.gemini_api_key and self.gemini_model)


def load_settings(env=None):
    env = os.environ if env is None else env
    data_dir = Path(env.get("DATA_DIR") or ROOT / "data")
    key = env.get("GEMINI_API_KEY", "").strip()
    embedder = env.get("EMBEDDER", "").strip().lower() or ("gemini" if key else "hashing")
    if embedder not in {"gemini", "hashing"}:
        raise ValueError("EMBEDDER must be 'gemini' or 'hashing'.")
    return Settings(
        database_url=env.get("DATABASE_URL") or f"sqlite:///{(data_dir / 'app.db').as_posix()}",
        data_dir=data_dir,
        gemini_api_key=key,
        gemini_model=env.get("GEMINI_MODEL", "").strip().removeprefix("models/"),
        embedder=embedder,
        embedding_model=env.get("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001").strip().removeprefix("models/"),
    )
