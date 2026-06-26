"""HuggingFace model search, local registry and background downloads.

Heavy deps (``huggingface_hub``) are imported lazily so the API boots without
them. A 14B model is ~28 GB, so downloads run on a background thread and the GUI
polls :func:`download_status` (which reports bytes-on-disk so a progress bar can
fill smoothly).
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ...core.config import settings

# Curated starting points for the "new project" picker. Kept in English on
# purpose. See docs/MODEL_SELECTION.md for the full rationale (Arabic quality,
# long context, QLoRA fit on 16 GB). Updated from the research pass.
CURATED_MODELS: list[dict[str, Any]] = [
    {
        "repo_id": "Qwen/Qwen3-14B",
        "label": "Qwen3-14B",
        "params": "14B",
        "context": "32K (131K w/ YaRN)",
        "arabic": "strong (119 langs)",
        "license": "Apache-2.0",
        "note": "Recommended default — newest Qwen that is actually 4-bit QLoRA-trainable on 16 GB. Best Arabic among QLoRA-viable models. Train at ~4K, serve longer via YaRN.",
        "recommended": True,
        "fast_4bit_repo": "unsloth/Qwen3-14B-unsloth-bnb-4bit",
        "default_seq_len": 4096,
        "default_lora_r": 16,
    },
    {
        "repo_id": "Qwen/Qwen3-8B",
        "label": "Qwen3-8B",
        "params": "8B",
        "context": "32K (131K w/ YaRN)",
        "arabic": "strong (119 langs)",
        "license": "Apache-2.0",
        "note": "Safest 16 GB fallback — ~2-3x more trainable context (~8-16K) and faster iteration. Cost-effective Arabic pick.",
        "recommended": False,
        "fast_4bit_repo": "unsloth/Qwen3-8B-unsloth-bnb-4bit",
        "default_seq_len": 8192,
        "default_lora_r": 32,
    },
    {
        "repo_id": "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B",
        "label": "DeepSeek-R1-0528-Qwen3-8B",
        "params": "8B",
        "context": "32K (131K w/ YaRN)",
        "arabic": "good (Qwen3-based)",
        "license": "MIT",
        "note": "Best DeepSeek-branded option — built on Qwen3-8B-Base so inherits Arabic. Always-on reasoning (cannot disable); pick for chain-of-thought tasks.",
        "recommended": False,
        "default_seq_len": 6144,
        "default_lora_r": 32,
    },
    {
        "repo_id": "Qwen/Qwen2.5-14B-Instruct-1M",
        "label": "Qwen2.5-14B-Instruct-1M",
        "params": "14B",
        "context": "1M (trained)",
        "arabic": "fair (29 langs)",
        "license": "Apache-2.0",
        "note": "Only pick for genuine >128K context needs. Weaker Arabic than Qwen3; serving true 1M needs huge VRAM.",
        "recommended": False,
        "default_seq_len": 4096,
        "default_lora_r": 16,
    },
    {
        # Constraint-relaxing: not Qwen/DeepSeek, but materially better native Arabic.
        "repo_id": "ALLaM-AI/ALLaM-7B-Instruct-preview",
        "label": "ALLaM-7B-Instruct (Arabic specialist)",
        "params": "7B",
        "context": "4K",
        "arabic": "excellent (native, ArabicMMLU ~67.8)",
        "license": "Apache-2.0",
        "note": "Best native Arabic (MSA + dialects) but only 4K context and NOT Qwen/DeepSeek-derived. Choose if Arabic cultural alignment outweighs long context.",
        "recommended": False,
        "default_seq_len": 4096,
        "default_lora_r": 32,
    },
    {
        "repo_id": "Navid-AI/Yehia-7B-preview",
        "label": "Yehia-7B (Arabic, AraGen-leading)",
        "params": "7B",
        "context": "4K",
        "arabic": "excellent (AraGen-leading)",
        "license": "Apache-2.0",
        "note": "ALLaM-based Arabic fine-tune topping AraGen. Same 4K limit; strongest Arabic if you relax the Qwen/DeepSeek constraint.",
        "recommended": False,
        "default_seq_len": 4096,
        "default_lora_r": 32,
    },
]


@dataclass
class Download:
    repo_id: str
    status: str = "pending"          # pending | downloading | done | error
    local_path: Optional[str] = None
    error: Optional[str] = None
    bytes_done: int = 0
    started: bool = False
    thread: Any = field(default=None, repr=False)


class DownloadManager:
    def __init__(self) -> None:
        self._downloads: dict[str, Download] = {}
        self._lock = threading.Lock()

    def _target_dir(self, repo_id: str) -> Path:
        return settings.models_dir / repo_id.replace("/", "__")

    def start(self, repo_id: str) -> Download:
        with self._lock:
            existing = self._downloads.get(repo_id)
            if existing and existing.status in ("pending", "downloading", "done"):
                return existing
            dl = Download(repo_id=repo_id)
            self._downloads[repo_id] = dl
            dl.thread = threading.Thread(target=self._run, args=(dl,), daemon=True)
            dl.thread.start()
            return dl

    def _run(self, dl: Download) -> None:
        dl.started = True
        dl.status = "downloading"
        target = self._target_dir(dl.repo_id)
        try:
            from huggingface_hub import snapshot_download
            local = snapshot_download(
                repo_id=dl.repo_id,
                local_dir=str(target),
                token=settings.hf_token,
                cache_dir=str(settings.hf_home),
            )
            dl.local_path = local
            dl.status = "done"
        except Exception as exc:  # pragma: no cover - network/env dependent
            dl.error = str(exc)
            dl.status = "error"

    def status(self, repo_id: str) -> dict[str, Any]:
        dl = self._downloads.get(repo_id)
        target = self._target_dir(repo_id)
        bytes_done = _dir_size(target)
        if dl is None:
            # Maybe it was downloaded in a previous session.
            if target.exists() and bytes_done > 0:
                return {"repo_id": repo_id, "status": "done",
                        "local_path": str(target), "bytes_done": bytes_done}
            return {"repo_id": repo_id, "status": "absent", "bytes_done": 0}
        return {
            "repo_id": repo_id,
            "status": dl.status,
            "local_path": dl.local_path or (str(target) if target.exists() else None),
            "error": dl.error,
            "bytes_done": bytes_done,
        }


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def list_local() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    base = settings.models_dir
    if not base.exists():
        return out
    for child in base.iterdir():
        if child.is_dir():
            out.append({
                "repo_id": child.name.replace("__", "/"),
                "local_path": str(child),
                "bytes": _dir_size(child),
            })
    return out


# ── HuggingFace access token ──────────────────────────────────────────────────
# The token lets us search/download gated or private repos. It can come from the
# environment (MISBAH_HF_TOKEN / .env) or be set at runtime from the GUI, in which
# case we persist it to a file under data/ and re-apply it on every boot. A
# UI-set file token takes precedence over the env value.

def _hf_token_path() -> Path:
    return settings.data_dir / "hf_token"


def _apply_token_runtime(token: Optional[str]) -> None:
    """Make ``token`` the effective one for this process (settings + HF env)."""
    settings.hf_token = token or None
    for var in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        if token:
            os.environ[var] = token
        else:
            os.environ.pop(var, None)


def apply_persisted_token() -> None:
    """Load a previously GUI-set token from disk and apply it. Best-effort; called
    at import so the very first request already has the token."""
    try:
        path = _hf_token_path()
        if path.exists():
            tok = path.read_text(encoding="utf-8").strip()
            if tok:
                _apply_token_runtime(tok)
    except OSError:
        pass


def whoami(token: Optional[str] = None) -> dict[str, Any]:
    """Validate a token against the Hub. Raises on an invalid/missing token."""
    from huggingface_hub import HfApi
    return HfApi(token=token or settings.hf_token).whoami()


def hf_token_status() -> dict[str, Any]:
    """Report whether a token is configured (no network call, no secret leak)."""
    tok = settings.hf_token
    source = "file" if _hf_token_path().exists() else ("env" if tok else None)
    return {
        "configured": bool(tok),
        "source": source,
        # A short, non-sensitive hint so the user can tell which token is set.
        "hint": (tok[:3] + "…" + tok[-4:]) if tok and len(tok) > 8 else None,
    }


def set_hf_token(token: str) -> dict[str, Any]:
    """Validate, persist and apply a HuggingFace token. Returns the username."""
    token = (token or "").strip()
    if not token:
        raise ValueError("Empty token.")
    info = whoami(token)                       # raises if the token is invalid
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    path = _hf_token_path()
    path.write_text(token, encoding="utf-8")
    try:
        os.chmod(path, 0o600)                  # best-effort: keep the secret private
    except OSError:
        pass
    _apply_token_runtime(token)
    return {"ok": True, "username": info.get("name") or info.get("fullname")}


def clear_hf_token() -> dict[str, Any]:
    """Remove a GUI-set token (reverts to the env value if any)."""
    try:
        _hf_token_path().unlink(missing_ok=True)
    except OSError:
        pass
    # Re-apply whatever the environment provides (None clears it entirely).
    _apply_token_runtime(os.environ.get("MISBAH_HF_TOKEN"))
    return {"ok": True}


def search(query: str, limit: int = 20) -> list[dict[str, Any]]:
    try:
        from huggingface_hub import HfApi
        api = HfApi(token=settings.hf_token)
        # huggingface_hub 1.x dropped the ``direction`` arg; sort="downloads"
        # already returns most-downloaded first.
        models = api.list_models(search=query, limit=limit, sort="downloads")
        return [{
            "repo_id": m.id,
            "downloads": getattr(m, "downloads", None),
            "likes": getattr(m, "likes", None),
            "tags": getattr(m, "tags", []) or [],
        } for m in models]
    except Exception as exc:  # pragma: no cover
        # Fall back to filtering the curated list so the picker still works offline.
        q = query.lower()
        return [m for m in CURATED_MODELS if q in m["repo_id"].lower() or q in m["label"].lower()] or [
            {"repo_id": query, "downloads": None, "likes": None, "tags": [], "note": str(exc)}
        ]


def search_datasets(query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Search the HuggingFace dataset hub (the training "corpus" picker).

    Mirrors :func:`search`; offline-friendly (returns a single echo row on error
    so the UI degrades gracefully instead of throwing). No torch import.
    """
    try:
        from huggingface_hub import HfApi
        api = HfApi(token=settings.hf_token)
        ds = api.list_datasets(search=query, limit=limit, sort="downloads")
        return [{
            "repo_id": d.id,
            "downloads": getattr(d, "downloads", None),
            "likes": getattr(d, "likes", None),
            "tags": getattr(d, "tags", []) or [],
        } for d in ds]
    except Exception as exc:  # pragma: no cover
        return [{"repo_id": query, "downloads": None, "likes": None, "tags": [], "note": str(exc)}]


def inspect_model(repo_id: str) -> dict[str, Any]:
    """Read a model's ``config.json`` from the Hub and normalize the fields the
    UI needs (architecture facts + MoE block). Used to validate a pretrained
    *embedding source* (hidden_size/vocab must match the new model) and to show
    architecture in the fine-tune path.

    Lightweight: downloads only the small config file via ``hf_hub_download`` —
    **no model instantiation, no torch**. Raises ``FileNotFoundError`` /
    ``PermissionError``-style exceptions which the router maps to clean HTTP codes.
    """
    import json as _json

    from huggingface_hub import hf_hub_download
    path = hf_hub_download(repo_id, "config.json", token=settings.hf_token,
                           cache_dir=str(settings.hf_home))
    cfg = _json.loads(Path(path).read_text(encoding="utf-8"))

    def g(*keys, default=None):
        for k in keys:
            if k in cfg and cfg[k] is not None:
                return cfg[k]
        return default

    num_experts = g("num_experts", "num_local_experts")
    is_moe = num_experts is not None or g("num_experts_per_tok") is not None
    return {
        "repo_id": repo_id,
        "model_type": g("model_type"),
        "architectures": g("architectures", default=[]),
        "num_hidden_layers": g("num_hidden_layers", "n_layer"),
        "hidden_size": g("hidden_size", "n_embd", "d_model"),
        "num_attention_heads": g("num_attention_heads", "n_head"),
        "num_key_value_heads": g("num_key_value_heads"),
        "intermediate_size": g("intermediate_size"),
        "vocab_size": g("vocab_size"),
        "max_position_embeddings": g("max_position_embeddings", "n_positions",
                                     "max_sequence_length"),
        "rope_theta": g("rope_theta"),
        "rope_scaling": g("rope_scaling"),
        "tie_word_embeddings": g("tie_word_embeddings", default=False),
        "torch_dtype": g("torch_dtype"),
        "quantization_config_present": "quantization_config" in cfg,
        "is_moe": is_moe,
        "num_experts": num_experts,
        "num_experts_per_tok": g("num_experts_per_tok"),
    }


def dataset_preview(repo_id: str, config: str | None = None,
                    split: str | None = None) -> dict[str, Any]:
    """Best-effort column/feature listing for a dataset so the UI can let the
    user pick a text field. Uses the public datasets-server HTTP API (no torch,
    no full download). Falls back to an empty column list with a note on error.
    """
    import urllib.parse
    import urllib.request
    import json as _json
    try:
        url = "https://datasets-server.huggingface.co/info?" + urllib.parse.urlencode(
            {"dataset": repo_id})
        headers = {}
        if settings.hf_token:
            headers["Authorization"] = f"Bearer {settings.hf_token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            info = _json.loads(resp.read().decode("utf-8"))
        configs = info.get("dataset_info", {})
        chosen = config or next(iter(configs), None)
        features = (configs.get(chosen, {}) or {}).get("features", {}) if chosen else {}
        columns = list(features.keys())
        string_cols = [c for c in columns
                       if str(features[c].get("dtype", "")).startswith("string")]
        # Rank string columns so the UI's auto-pick lands on the real body text,
        # not a short metadata column (author, title, dynasty, label, …). Known
        # body-text names first (by preference order), then any other string col.
        preferred = ("text", "content", "document", "body", "article", "passage",
                     "sentence", "verse_text", "poem", "story", "review",
                     "output", "completion", "response", "answer",
                     "prompt", "instruction", "input", "question")
        ranked = [c for name in preferred for c in string_cols if c.lower() == name]
        ranked += [c for c in string_cols if c not in ranked]
        return {"repo_id": repo_id, "configs": list(configs.keys()),
                "config": chosen, "columns": columns,
                "text_field_candidates": ranked or columns}
    except Exception as exc:  # pragma: no cover - network dependent
        return {"repo_id": repo_id, "configs": [], "config": None,
                "columns": [], "text_field_candidates": [], "note": str(exc)}


manager = DownloadManager()

# Re-apply a GUI-set token (if any) so the first search/download is authenticated.
apply_persisted_token()
