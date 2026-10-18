#!/usr/bin/env python3
"""PostToolUse hook: enforce the mechanical rules from CLAUDE.md.

Runs after Edit/Write/MultiEdit. Reads the touched file and scans for the
violations that are cheap to detect with a regex. Exits 2 with the violated
rule on stderr, which Claude Code feeds back to the model so it fixes the
problem before moving on.

Rules that need real understanding (vertical slicing, dead code, deprecated
APIs) are not checked here -- they belong to `cleaner` and code review.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

# ---------------------------------------------------------------- rule model


@dataclass(frozen=True)
class Rule:
    id: str
    pattern: re.Pattern[str]
    message: str
    applies: Callable[[Path], bool]


def is_feature_scss(path: Path) -> bool:
    if path.suffix != ".scss":
        return False
    # `_tokens.scss` defines the tokens, `_layout.scss` holds the page width and the
    # shell's breakpoints, and `_reset.scss` is where the ladder touches the ground.
    # Everything else reads tokens.
    return path.name not in {"_tokens.scss", "_layout.scss", "_reset.scss"}


def is_frontend_ts(path: Path) -> bool:
    return path.suffix == ".ts" and ".spec." not in path.name


def is_frontend_template(path: Path) -> bool:
    return path.suffix == ".html" and "src" in path.parts and "app" in path.parts


def is_declaration_free_ts(path: Path) -> bool:
    return path.suffix == ".ts" and not path.name.endswith((".types.ts", ".d.ts"))


def is_backend_python(path: Path) -> bool:
    return path.suffix == ".py" and "backend" in path.parts and "migrations" not in path.parts


def is_currency_bearing(path: Path) -> bool:
    if ".spec." in path.name or "migrations" in path.parts:
        return False
    if path.name in {"en.json", "ar.json"}:
        return True
    if path.suffix in {".ts", ".html"} and "src" in path.parts:
        return True
    return path.suffix == ".py" and "apps" in path.parts


def is_user_facing_arabic(path: Path) -> bool:
    # The Arabic catalogues, and the seed migrations that carry an `_ar` column.
    # Test fixtures may quote a source as it was printed, so they are not checked.
    if path.name == "ar.json":
        return True
    return path.suffix == ".py" and "migrations" in path.parts


def is_django_app_python(path: Path) -> bool:
    if path.suffix != ".py":
        return False
    parts = path.parts
    if "apps" not in parts:
        return False
    # Repositories are the one place the ORM is allowed.
    if "repositories" in parts:
        return False
    # Migrations are generated and legitimately reference the ORM.
    if "migrations" in parts:
        return False
    return True


RULES: tuple[Rule, ...] = (
    Rule(
        id="RULE 12 (Angular)",
        pattern=re.compile(r":[^;{}]*?(?<![\w.-])\d+(?:\.\d+)?px\b"),
        message=(
            "raw px in a feature stylesheet.\n"
            "  Colour, type, shape and elevation are Material's system tokens: use\n"
            "  var(--mat-sys-*), set by the theme in src/styles/_theme.scss. Spacing is\n"
            "  var(--app-space-*) from src/styles/_tokens.scss. Never a literal px value."
        ),
        applies=is_feature_scss,
    ),
    Rule(
        id="RULE 22e (Language)",
        pattern=re.compile("[\u064b-\u0652\u0670]"),
        message=(
            "tashkeel in Arabic a user reads.\n"
            "  No diacritic in any ar.json value or seeded _ar column. A word that needs\n"
            "  a vowel mark to be read is the wrong word - replace it, do not strip the\n"
            "  mark. See .claude/docs/language.md."
        ),
        applies=is_user_facing_arabic,
    ),
    Rule(
        id="RULE 10 (Angular)",
        pattern=re.compile(r"\bsetTimeout\s*\("),
        message=(
            "setTimeout is not allowed.\n"
            "  Model the timing in state with signals, or let CSS express the delay."
        ),
        applies=is_frontend_ts,
    ),
    Rule(
        id="RULE 9 (Angular)",
        pattern=re.compile(r"(?:\bwindow\s*\.\s*)?\b(?:confirm|alert|prompt)\s*\("),
        message=(
            "native browser dialog.\n"
            "  Ask with MatDialog for confirm(), report with MatSnackBar or a role=\"alert\"\n"
            "  message in the page for alert(), and collect with a mat-form-field for prompt()."
        ),
        applies=is_frontend_ts,
    ),
    Rule(
        id="RULE 9 (Angular)",
        pattern=re.compile(
            r"<dialog[\s>]|<select[\s>]|<input[^>]*\btype\s*=\s*[\"'](?:radio|checkbox)[\"']"
        ),
        message=(
            "a native control Angular Material draws.\n"
            "  Use MatDialog for <dialog>, mat-select for <select>, mat-radio-group for a\n"
            "  radio and mat-checkbox or mat-slide-toggle for a checkbox."
        ),
        applies=is_frontend_template,
    ),
    Rule(
        id="RULE 29 (Currency)",
        pattern=re.compile("\\bOMR\\b|\\bO\\.\\s?R\\.|\\bR\\.\\s?O\\.|\u0631\\.\\s?\u0639|\ufdfc"),
        message=(
            "an old way of writing the Omani rial.\n"
            "  Amounts render through <app-money>, which draws the Central Bank of Oman's\n"
            "  sign (U+20C4). Never OMR, O.R., R.O., the Arabic abbreviation or the\n"
            "  generic rial sign, in a template, a bundle or the API."
        ),
        applies=is_currency_bearing,
    ),
    Rule(
        id="RULE 30 (TypeScript)",
        pattern=re.compile(r"(?::|\bas|<|\||&|,)\s*any\b(?!-)|\bany\[\]|<any>"),
        message=(
            "`any` in TypeScript.\n"
            "  Name the type. When it is truly unknown, use `unknown` and narrow it."
        ),
        applies=is_frontend_ts,
    ),
    Rule(
        id="RULE 30 (TypeScript)",
        pattern=re.compile(
            r"^\s*(?:export\s+)?(?:declare\s+)?(?:interface\s+\w+|type\s+\w+\s*(?:<[^>]*>)?\s*=)"
        ),
        message=(
            "an interface or type alias outside a types file.\n"
            "  Declarations live in a sibling `<name>.types.ts`, and the code imports them\n"
            "  with `import type`."
        ),
        applies=is_declaration_free_ts,
    ),
    Rule(
        id="RULE 14 (Django)",
        pattern=re.compile(r"\.objects\s*\."),
        message=(
            "ORM access outside a repository.\n"
            "  Every .objects. call belongs in apps/<feature>/repositories/.\n"
            "  Views call services; services call repositories; repositories call the ORM."
        ),
        applies=is_django_app_python,
    ),
    Rule(
        id="RULE 14 (Django)",
        pattern=re.compile(r"\b(?:raw|extra)\s*\(\s*[\"']|\bcursor\s*\.\s*execute\s*\("),
        message=(
            "raw SQL in application code.\n"
            "  Express it through the ORM. If that is genuinely impossible, put it in a\n"
            "  repository method with a comment explaining why, and have db_engineer\n"
            "  sign off with benchmark numbers."
        ),
        applies=is_django_app_python,
    ),
    Rule(
        id="RULE 16 (Django)",
        pattern=re.compile(r"\.hard_delete\s*\(|\bqueryset\s*\.\s*delete\s*\(\s*\)"),
        message=(
            "hard delete.\n"
            "  delete() must set deleted_at. Removing rows for real is a data migration,\n"
            "  never an application action."
        ),
        applies=is_django_app_python,
    ),
)

# ------------------------------------------------------------------- scanning

COMMENT_PREFIXES = ("//", "#", "*", "/*", "<!--")


def offending_lines(text: str, rule: Rule) -> Iterable[tuple[int, str]]:
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(COMMENT_PREFIXES):
            continue
        if rule.pattern.search(line):
            yield number, stripped


def star_imported_names(path: Path, tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
            if not any(alias.name == "*" for alias in node.names):
                continue
            sibling: Path = path.parent / f"{node.module}.py"
            try:
                names |= declared_at_top(ast.parse(sibling.read_text(encoding="utf-8")))
            except (OSError, SyntaxError):
                continue
    return names


def declared_at_top(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.Import | ast.ImportFrom):
            names |= {(alias.asname or alias.name).split(".")[0] for alias in node.names}
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
    return names


def unannotated_assignments(body: list[ast.stmt], declared: set[str]) -> Iterable[ast.Assign]:
    for node in body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            arguments: ast.arguments = node.args
            params: list[ast.arg] = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
            params += [extra for extra in (arguments.vararg, arguments.kwarg) if extra]
            yield from unannotated_assignments(node.body, declared | {a.arg for a in params})
            continue
        if isinstance(node, ast.ClassDef):
            for member in node.body:
                if isinstance(member, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                    yield from unannotated_assignments([member], set(declared))
            continue
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            declared.add(node.target.id)
        elif isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id not in declared for t in node.targets):
                yield node
        elif isinstance(node, ast.Import | ast.ImportFrom):
            declared |= {(alias.asname or alias.name).split(".")[0] for alias in node.names}
        for nested in ("body", "orelse", "finalbody"):
            inner: object = getattr(node, nested, None)
            if isinstance(inner, list):
                yield from unannotated_assignments(inner, declared)
        for handler in getattr(node, "handlers", []):
            yield from unannotated_assignments(handler.body, declared)
        for case in getattr(node, "cases", []):
            yield from unannotated_assignments(case.body, declared)


def untyped_variables(path: Path, text: str) -> list[str]:
    if not is_backend_python(path):
        return []
    try:
        tree: ast.Module = ast.parse(text)
    except SyntaxError:
        return []
    found: list[str] = []
    for node in unannotated_assignments(tree.body, star_imported_names(path, tree)):
        names: str = ", ".join(t.id for t in node.targets if isinstance(t, ast.Name))
        found.append(
            "RULE 30 (Python): a variable without a type.\n"
            "  Annotate it where it is first bound: `name: Type = value`.\n"
            f"  {path}:{node.lineno}\n    {names}"
        )
    return found


def is_application_code(path: Path) -> bool:
    if "migrations" in path.parts:
        return False
    if path.suffix == ".py":
        return "backend" in path.parts
    return path.suffix in {".ts", ".html", ".scss"} and ("src" in path.parts or "e2e" in path.parts)


COMMENT_LINE = re.compile(r"^\s*(?:#(?!!)|//|/\*|<!--)")
PRAGMA = re.compile(r"noqa|type:\s*ignore|eslint-disable|@ts-|pragma")


def heavy_comments(path: Path, text: str) -> list[str]:
    if not is_application_code(path):
        return []
    found: list[str] = []
    if path.suffix == ".py":
        try:
            tree: ast.Module = ast.parse(text)
        except SyntaxError:
            tree = ast.Module(body=[], type_ignores=[])
        owners: list[ast.AST] = [tree, *ast.walk(tree)]
        for owner in owners:
            body: object = getattr(owner, "body", None)
            if not isinstance(owner, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if isinstance(body, list) and body and isinstance(body[0], ast.Expr):
                value: ast.expr = body[0].value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    found.append(
                        "RULE 31 (Comments): a docstring.\n"
                        "  Describe the class or method in the module's CLAUDE.md, under\n"
                        "  `## Classes and methods`, and delete the docstring.\n"
                        f"  {path}:{body[0].lineno}"
                    )
    run: list[int] = []
    open_block: str | None = None
    lines: list[str] = text.splitlines()
    for number, line in enumerate([*lines, ""], start=1):
        stripped: str = line.strip()
        is_comment: bool = open_block is not None
        is_comment = is_comment or bool(COMMENT_LINE.match(line)) and not PRAGMA.search(line)
        for opener, closer in (("<!--", "-->"), ("/*", "*/")):
            if open_block is None and stripped.startswith(opener) and closer not in stripped:
                open_block = closer
            elif open_block == closer and closer in stripped:
                open_block = None
        if stripped.startswith("/**"):
            found.append(
                "RULE 31 (Comments): a JSDoc block.\n"
                "  Describe it in the module's CLAUDE.md instead.\n"
                f"  {path}:{number}"
            )
        if is_comment and stripped:
            run.append(number)
            continue
        if len(run) > 2:
            found.append(
                f"RULE 31 (Comments): a {len(run)}-line comment.\n"
                "  Keep a comment to one or two lines saying why; anything longer belongs in\n"
                "  the module's CLAUDE.md.\n"
                f"  {path}:{run[0]}"
            )
        run = []
    return found


def touched_path(event: dict) -> Path | None:
    tool_input = event.get("tool_input") or {}
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not raw:
        return None
    return Path(raw)


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    path = touched_path(event)
    if path is None:
        return 0

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0

    violations: list[str] = []
    for rule in RULES:
        if not rule.applies(path):
            continue
        for number, line in offending_lines(text, rule):
            violations.append(f"{rule.id}: {rule.message}\n  {path}:{number}\n    {line}")
    violations += untyped_variables(path, text)
    violations += heavy_comments(path, text)

    if not violations:
        return 0

    header = f"Blocked: {len(violations)} rule violation(s) in {path.name}."
    body = "\n\n".join(violations)
    footer = "See .claude/docs/design-pattern.md. Fix these before continuing."
    print(f"{header}\n\n{body}\n\n{footer}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
