from __future__ import annotations

import argparse
import hashlib
import html
import json
import shutil
import sys
import tarfile
import tempfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

PASSED: frozenset[str] = frozenset({"success", "skipped"})


def pairs(values: list[str], what: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for value in values:
        name, separator, rest = value.partition("=")
        if not separator or not name:
            raise ValueError(f"{what} {value!r} is not name=value")
        found[name] = rest
    return found


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inventory(root: Path) -> list[dict[str, object]]:
    return [
        {"path": str(path.relative_to(root)), "bytes": path.stat().st_size, "sha256": digest(path)}
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def gallery(root: Path, version: str) -> str:
    images: list[Path] = sorted(root.rglob("*.png"))
    sections: dict[str, list[Path]] = {}
    for image in images:
        sections.setdefault(str(image.parent.relative_to(root)), []).append(image)
    body: list[str] = []
    for title, shown in sections.items():
        body.append(f"<h2>{html.escape(title)}</h2>")
        body.extend(
            f'<figure><img src="{html.escape(str(image.relative_to(root)))}" loading="lazy" '
            f'alt=""><figcaption>{html.escape(image.stem)}</figcaption></figure>'
            for image in shown
        )
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        f"<title>Mesbah {html.escape(version)} journeys</title>"
        "<style>body{font-family:sans-serif;margin:1rem}figure{display:inline-block;margin:.5rem;"
        "max-width:24rem}img{max-width:100%;border:1px solid #ccc}</style>"
        f"<h1>Mesbah {html.escape(version)}: what the journeys saw</h1>{''.join(body)}</html>\n"
    )


def summary(version: str, results: dict[str, str], extras: dict[str, str]) -> str:
    lines: list[str] = [f"# Mesbah {version}: release bundle", "", "| Part | Result |", "|---|---|"]
    lines += [f"| {name} | {result} |" for name, result in results.items()]
    lines += ["", *[f"- **{name}**: {value}" for name, value in extras.items()]]
    return "\n".join(lines) + "\n"


def assemble(
    version: str,
    out: Path,
    parts: dict[str, Path],
    results: dict[str, str],
    extras: dict[str, str],
) -> Path:
    with tempfile.TemporaryDirectory() as scratch:
        root: Path = Path(scratch) / f"mesbah-{version}-reference"
        root.mkdir()
        for name, source in parts.items():
            if source.is_dir():
                shutil.copytree(source, root / name)
            elif source.is_file():
                (root / name).mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, root / name / source.name)
        screens: Path = root / "e2e" / "screens"
        if screens.is_dir():
            (screens / "index.html").write_text(gallery(screens, version), encoding="utf-8")
        (root / "summary.md").write_text(summary(version, results, extras), encoding="utf-8")
        manifest: dict[str, object] = {
            "version": version,
            "made": datetime.now(UTC).isoformat(timespec="seconds"),
            "results": results,
            **extras,
            "files": inventory(root),
        }
        (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        out.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(out, "w:gz") as archive:
            archive.add(root, arcname=root.name)
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="python -m tools.release.reference"
    )
    parser.add_argument("--version", required=True, help="the version, as SemVer")
    parser.add_argument("--out", type=Path, required=True, help="the tarball to write")
    parser.add_argument("--part", action="append", default=[], help="name=folder or file")
    parser.add_argument("--result", action="append", default=[], help="job=result")
    parser.add_argument("--note", action="append", default=[], help="key=value for the manifest")
    arguments: argparse.Namespace = parser.parse_args(argv)
    try:
        parts: dict[str, Path] = {
            name: Path(source) for name, source in pairs(arguments.part, "part").items()
        }
        results: dict[str, str] = pairs(arguments.result, "result")
        extras: dict[str, str] = pairs(arguments.note, "note")
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    written: Path = assemble(arguments.version, arguments.out, parts, results, extras)
    failed: list[str] = [name for name, result in results.items() if result not in PASSED]
    print(f"{written} ({written.stat().st_size} bytes)")
    if failed:
        print(f"error: these parts did not pass: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
