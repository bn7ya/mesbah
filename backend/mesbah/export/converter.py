from __future__ import annotations

import hashlib
from pathlib import Path

import httpx2

LLAMA_CPP_TAG: str = "b9000"
SOURCE: str = f"https://raw.githubusercontent.com/ggml-org/llama.cpp/{LLAMA_CPP_TAG}/"
# The last release whose converter is one file; its own gguf-py rides along, so the
# converter never meets a gguf package of another version.
CONVERTER: str = "convert_hf_to_gguf.py"
GGUF_PY: str = "gguf-py/gguf/"
GGUF_PY_FILES: dict[str, str] = {
    "__init__.py": "3ccfc0104cd7ea88c6028743b7bf3f2c89b5f474425de03a217a6072320d7c2f",
    "constants.py": "cff2cb8d576d45fd2a270f5fc773115cadf4791e7301d10a4452f99c70686d8c",
    "gguf.py": "f0c0eeedad0911784b52ffed8e162a0eb5ae6d535ce35705bc16196e46597a72",
    "gguf_reader.py": "91cb9e81f1a67f5856f012cf3f526ad9ffdb6b887d2aa66e2593ee6f63764aad",
    "gguf_writer.py": "572d1b5723e1c688b2e4d25f9957c7eaae8eaec84c34fab0710a94096113c8ff",
    "lazy.py": "ec35541320443e1bdc293e39c699fa5d1adb7fb594f3f87af093b4c756a4ebe2",
    "metadata.py": "c871748f49f7fb8e67aa9a18867adf8a8ba862f0f1f4a89a0a0e285daa52a312",
    "py.typed": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "quants.py": "db403c3b2292d3f2c5cfef4109d4b5745f437b5599c7afc94d4b97feca7e9247",
    "tensor_mapping.py": "46c212cb8c3aba23fb745c1e3be3228c0df407a202b6bbe10a5506e5714d7fe2",
    "utility.py": "da920e2c62166ec9f30e407e9fb35ec29fda671310ffbf0f8ce856b62f1c70d7",
    "vocab.py": "c3a6ddea051579d48e1a591c1cb481bddd4439b756952531a25c4cddf6382b97",
}
FILES: dict[str, str] = {
    CONVERTER: "3ff05b62f65c16c1864ee3439b692aa6f184f5e18356f94ae2ebe1c7427644d4",
    **{GGUF_PY + name: digest for name, digest in GGUF_PY_FILES.items()},
}
TIMEOUT: float = 60.0


class ConverterUnavailable(Exception):
    pass


def converter(tools_dir: Path, client: httpx2.Client | None = None) -> Path:
    home: Path = tools_dir / f"llama.cpp-{LLAMA_CPP_TAG}"
    missing: list[str] = [
        name for name, digest in FILES.items() if not _intact(home / name, digest)
    ]
    if missing:
        owned: bool = client is None
        session: httpx2.Client = client or httpx2.Client(timeout=TIMEOUT, follow_redirects=True)
        try:
            for name in missing:
                _fetch(session, name, home / name)
        finally:
            if owned:
                session.close()
    return home / CONVERTER


def _fetch(session: httpx2.Client, name: str, target: Path) -> None:
    try:
        response: httpx2.Response = session.get(SOURCE + name)
    except httpx2.HTTPError as error:
        raise ConverterUnavailable(f"{name}: {error}") from error
    if not response.is_success:
        raise ConverterUnavailable(f"{name}: HTTP {response.status_code}")
    if hashlib.sha256(response.content).hexdigest() != FILES[name]:
        raise ConverterUnavailable(f"{name}: the download does not match its pinned digest")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(response.content)


def _intact(path: Path, digest: str) -> bool:
    return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == digest
