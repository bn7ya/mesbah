"""Application configuration.

All paths and tunables live here. Values can be overridden with environment
variables (see ``backend/.env.example``). Technical terms are kept in English on
purpose so the codebase stays portable; user-facing strings live in the frontend.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# ── Repo / data layout ────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parents[2]   # .../backend
DATA_DIR = BACKEND_DIR / "data"


class Settings(BaseSettings):
    """Runtime settings, populated from env (prefix ``MISBAH_``) or defaults."""

    model_config = SettingsConfigDict(
        env_prefix="MISBAH_",
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ──
    app_name: str = "Misbah — LLM Fine-tuning Studio"
    debug: bool = True
    host: str = "127.0.0.1"
    port: int = 8077   # 8000 is commonly taken by Django; pick a quieter port
    # Angular dev server origins allowed for CORS.
    cors_origins: list[str] = Field(default=["http://localhost:4200", "http://127.0.0.1:4200"])

    # ── Storage ──
    data_dir: Path = DATA_DIR
    database_url: str = f"sqlite:///{DATA_DIR / 'misbah.db'}"

    # ── HuggingFace ──
    hf_token: str | None = None
    hf_home: Path = DATA_DIR / "hf_cache"
    # Curated default base model — see docs/MODEL_SELECTION.md. Overridable per project.
    default_base_model: str = "Qwen/Qwen3-14B"

    # ── Hardware budget (RTX 5080 / 16 GB) ──
    gpu_vram_gb: int = 16
    # Hard ceiling the UI warns past; QLoRA defaults are tuned for this card.
    max_train_seq_len: int = 4096

    # ── Inference defaults ──
    infer_max_new_tokens: int = 1024
    infer_temperature: float = 0.7
    infer_top_p: float = 0.9

    # ── Derived data sub-dirs (created on startup) ──
    @property
    def models_dir(self) -> Path:        # downloaded base models
        return self.data_dir / "models"

    @property
    def adapters_dir(self) -> Path:      # LoRA adapters per model version
        return self.data_dir / "adapters"

    @property
    def datasets_dir(self) -> Path:      # generated training datasets (jsonl)
        return self.data_dir / "datasets"

    @property
    def runs_dir(self) -> Path:          # per-training-run logs + metrics.jsonl
        return self.data_dir / "runs"

    @property
    def offload_dir(self) -> Path:       # disk spillover when VRAM + RAM are full
        return self.data_dir / "offload"

    def ensure_dirs(self) -> None:
        for p in (self.data_dir, self.hf_home, self.models_dir, self.adapters_dir,
                  self.datasets_dir, self.runs_dir, self.offload_dir):
            p.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
