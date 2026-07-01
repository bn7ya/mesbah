"""HuggingFace model search, local registry and background downloads.

Heavy deps (``huggingface_hub``) are imported lazily so the API boots without
them. A 14B model is ~28 GB, so downloads run on a background thread and the GUI
polls :func:`download_status` (which reports bytes-on-disk so a progress bar can
fill smoothly).
"""
from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ...core.config import settings


@dataclass
class Download:
    repo_id: str
    repo_type: str = "model"          # "model" | "dataset"
    status: str = "pending"          # pending | downloading | done | error
    local_path: Optional[str] = None
    error: Optional[str] = None
    bytes_done: int = 0
    total_bytes: int = 0              # 0 until the Hub metadata lookup lands
    started: bool = False
    thread: Any = field(default=None, repr=False)


class DownloadManager:
    """Background snapshot downloads for **models and datasets**, with a real
    total-size lookup so the GUI can show a percentage bar (not just bytes-on-disk).
    """

    def __init__(self) -> None:
        self._downloads: dict[str, Download] = {}
        self._lock = threading.Lock()

    def _key(self, repo_id: str, repo_type: str) -> str:
        return f"{repo_type}:{repo_id}"

    def _target_dir(self, repo_id: str, repo_type: str = "model") -> Path:
        sub = repo_id.replace("/", "__")
        if repo_type == "dataset":
            # keep downloaded HF datasets out of the generated-jsonl datasets_dir
            return settings.datasets_dir / "_hf" / sub
        return settings.models_dir / sub

    def start(self, repo_id: str, repo_type: str = "model") -> Download:
        with self._lock:
            key = self._key(repo_id, repo_type)
            existing = self._downloads.get(key)
            if existing and existing.status in ("pending", "downloading", "done"):
                return existing
            dl = Download(repo_id=repo_id, repo_type=repo_type)
            self._downloads[key] = dl
            dl.thread = threading.Thread(target=self._run, args=(dl,), daemon=True)
            dl.thread.start()
            return dl

    def _run(self, dl: Download) -> None:
        dl.started = True
        dl.status = "downloading"
        target = self._target_dir(dl.repo_id, dl.repo_type)
        # Best-effort total size up front so the progress bar has a denominator.
        try:
            dl.total_bytes = _repo_total_bytes(dl.repo_id, dl.repo_type)
        except Exception:
            dl.total_bytes = 0
        try:
            from huggingface_hub import snapshot_download
            local = snapshot_download(
                repo_id=dl.repo_id,
                repo_type=dl.repo_type,
                local_dir=str(target),
                token=settings.hf_token,
                cache_dir=str(settings.hf_home),
            )
            dl.local_path = local
            dl.status = "done"
        except Exception as exc:  # pragma: no cover - network/env dependent
            dl.error = str(exc)
            dl.status = "error"

    def status(self, repo_id: str, repo_type: str = "model") -> dict[str, Any]:
        dl = self._downloads.get(self._key(repo_id, repo_type))
        target = self._target_dir(repo_id, repo_type)
        bytes_done = _dir_size(target)
        if dl is None:
            # Maybe it was downloaded in a previous session.
            if target.exists() and bytes_done > 0:
                return {"repo_id": repo_id, "repo_type": repo_type, "status": "done",
                        "local_path": str(target), "bytes_done": bytes_done,
                        "total_bytes": bytes_done, "percent": 100.0}
            return {"repo_id": repo_id, "repo_type": repo_type, "status": "absent",
                    "bytes_done": 0, "total_bytes": 0, "percent": 0.0}
        total = dl.total_bytes or 0
        if dl.status == "done":
            percent = 100.0
        elif total:
            percent = round(min(100.0, bytes_done / total * 100), 1)
        else:
            percent = 0.0
        return {
            "repo_id": repo_id,
            "repo_type": repo_type,
            "status": dl.status,
            "local_path": dl.local_path or (str(target) if target.exists() else None),
            "error": dl.error,
            "bytes_done": bytes_done,
            "total_bytes": total,
            "percent": percent,
        }

    def list_all(self) -> list[dict[str, Any]]:
        """Status of every download tracked this session (for the global GUI chip)."""
        with self._lock:
            entries = list(self._downloads.values())
        return [self.status(dl.repo_id, dl.repo_type) for dl in entries]


def _repo_total_bytes(repo_id: str, repo_type: str = "model") -> int:
    """Sum of all file sizes in a Hub repo (one metadata call; best-effort)."""
    from huggingface_hub import HfApi
    info = HfApi(token=settings.hf_token).repo_info(
        repo_id=repo_id, repo_type=repo_type, files_metadata=True)
    total = 0
    for s in (info.siblings or []):
        size = getattr(s, "size", None)
        if size:
            total += int(size)
    return total


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


# ── Live model listing (no hardcoded catalog) ─────────────────────────────────
# The models page and the new-project picker are populated straight from the
# HuggingFace Hub. Results are cached in-process for a short TTL so the GUI
# doesn't hammer the Hub; when the Hub is unreachable we degrade to the locally
# downloaded models so the picker keeps working offline.

_FEATURED_TTL_SECONDS = 15 * 60
_featured_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_featured_lock = threading.Lock()

_PARAMS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[bB]\b")


def _params_from_name(repo_id: str) -> Optional[str]:
    """Best-effort parameter count from the repo name (``Qwen3-14B`` → ``14B``)."""
    m = _PARAMS_RE.search(repo_id.rsplit("/", 1)[-1].replace("_", "-"))
    return f"{m.group(1)}B" if m else None


def _license_from_tags(tags: list[str]) -> Optional[str]:
    for t in tags:
        if t.startswith("license:"):
            return t.split(":", 1)[1]
    return None


def _hub_model(m: Any) -> dict[str, Any]:
    """Normalize a ``huggingface_hub`` model hit to the shape the GUI renders."""
    repo_id = m.id
    tags = list(getattr(m, "tags", []) or [])
    return {
        "repo_id": repo_id,
        "label": repo_id.rsplit("/", 1)[-1],
        "downloads": getattr(m, "downloads", None),
        "likes": getattr(m, "likes", None),
        "tags": tags,
        "license": _license_from_tags(tags),
        "params": _params_from_name(repo_id),
        "pipeline_tag": getattr(m, "pipeline_tag", None),
        "gated": bool(getattr(m, "gated", False)),
        "source": "hub",
    }


def _local_as_hub_models(note: str | None = None) -> list[dict[str, Any]]:
    """Locally downloaded models mapped to the featured shape (offline fallback)."""
    out = []
    for m in list_local():
        out.append({
            "repo_id": m["repo_id"],
            "label": m["repo_id"].rsplit("/", 1)[-1],
            "downloads": None,
            "likes": None,
            "tags": [],
            "license": None,
            "params": _params_from_name(m["repo_id"]),
            "pipeline_tag": None,
            "gated": False,
            "source": "local",
            **({"note": note} if note else {}),
        })
    return out


def list_featured(limit: int = 12, language: str | None = None) -> list[dict[str, Any]]:
    """Most-downloaded text-generation models, live from the HF API.

    ``language="ar"`` powers the Arabic section. Cached for ~15 min; on any hub
    error returns the local registry (``source: "local"``) — never raises.
    """
    key = f"{limit}:{language or ''}"
    now = time.time()
    with _featured_lock:
        hit = _featured_cache.get(key)
        if hit and now - hit[0] < _FEATURED_TTL_SECONDS:
            return hit[1]
    try:
        from huggingface_hub import HfApi
        api = HfApi(token=settings.hf_token)
        # Language codes are plain tags on the Hub; hub 1.x dropped the
        # ``language=`` kwarg, so filter by tag (works on 0.x too).
        models = api.list_models(
            pipeline_tag="text-generation",
            filter=language or None,
            sort="downloads",
            limit=limit,
        )
        out = [_hub_model(m) for m in models]
        with _featured_lock:
            _featured_cache[key] = (now, out)
        return out
    except Exception as exc:  # pragma: no cover - network dependent
        return _local_as_hub_models(note=str(exc))


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
        # Fall back to filtering the local registry so the picker still works offline.
        q = query.lower()
        local = [m for m in _local_as_hub_models() if q in m["repo_id"].lower()]
        return local or [
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
