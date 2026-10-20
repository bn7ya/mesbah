from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

BACKEND: Path = Path(__file__).resolve().parents[1]
REPOSITORY: Path = BACKEND.parent
FRONTEND: Path = REPOSITORY / "frontend"
SPA_BUILD: Path = FRONTEND / "dist" / "frontend" / "browser"
SPA_TARGET: Path = BACKEND / "mesbah" / "_spa"


def run(command: list[str], cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)  # noqa: S603


def main() -> int:
    if "--skip-frontend" not in sys.argv:
        npm: str = shutil.which("npm") or "npm"
        run([npm, "ci", "--no-audit", "--no-fund"], FRONTEND)
        run([npm, "run", "build", "--", "--configuration", "production"], FRONTEND)
    if not (SPA_BUILD / "index.html").is_file():
        print(f"No built frontend at {SPA_BUILD}.", file=sys.stderr)
        return 1
    shutil.rmtree(SPA_TARGET, ignore_errors=True)
    shutil.copytree(SPA_BUILD, SPA_TARGET)
    shutil.copyfile(REPOSITORY / "LICENSE", BACKEND / "LICENSE")
    out: str = os.environ.get("MESBAH_DIST", str(BACKEND / "dist"))
    run([sys.executable, "-m", "build", "--outdir", out, str(BACKEND)], BACKEND)
    return 0


if __name__ == "__main__":
    sys.exit(main())
