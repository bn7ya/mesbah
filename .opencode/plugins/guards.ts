/**
 * Port of `.claude/hooks/guard-checks.py` for opencode.
 *
 * The Claude hook runs after the edit (PostToolUse) and reports violations. This
 * runs *before* the edit lands (`tool.execute.before`) and throws, so a
 * violating edit never reaches disk and the model gets the rule back to fix.
 *
 * The rules are the mechanical hard rules from CLAUDE.md:
 *   - raw px in feature styles          (rule 12)
 *   - tashkeel in user-facing Arabic    (rule 22e)
 *   - setTimeout in frontend ts         (rule 10)
 *   - native dialogs / native controls  (rule 9)
 *   - .objects. / raw SQL outside repos (rule 14)
 *   - hard delete                       (rule 16)
 *
 * The judgement rules (vertical slicing, dead code, deprecated APIs) are not
 * checked here — they belong to `cleaner` and review, exactly as in the
 * original hook.
 */

import type { Plugin } from "@opencode-ai/plugin";
import { readFileSync, existsSync } from "node:fs";
import { isAbsolute, join, parse as parsePath } from "node:path";

// --------------------------------------------------------------- path helpers

type P = { suffix: string; name: string; parts: string[] };

function toP(absPath: string): P {
  const parsed = parsePath(absPath);
  // Mirror pathlib: parts are the path segments (no drive/root handling needed
  // for the predicates below, which only look at a small set of names).
  const parts = absPath.split("/").filter(Boolean);
  return { suffix: parsed.ext, name: parsed.base, parts };
}

function hasPart(parts: string[], name: string): boolean {
  return parts.includes(name);
}

// -------------------------------------------------------------------- applies

function isFeatureScss(p: P): boolean {
  if (p.suffix !== ".scss") return false;
  // The --app-* definitions, the breakpoints and the reset may hold raw values.
  return !["_tokens.scss", "_layout.scss", "_reset.scss"].includes(p.name);
}

function isUserFacingArabic(p: P): boolean {
  if (p.name === "ar.json") return true;
  return p.suffix === ".py" && hasPart(p.parts, "migrations");
}

function isFrontendTs(p: P): boolean {
  return p.suffix === ".ts" && !p.name.includes(".spec.");
}

function isFrontendTemplate(p: P): boolean {
  return p.suffix === ".html" && hasPart(p.parts, "src") && hasPart(p.parts, "app");
}

function isDjangoAppPython(p: P): boolean {
  if (p.suffix !== ".py") return false;
  if (!hasPart(p.parts, "apps")) return false;
  // Repositories are the one place the ORM is allowed.
  if (hasPart(p.parts, "repositories")) return false;
  // Migrations are generated and legitimately reference the ORM.
  if (hasPart(p.parts, "migrations")) return false;
  return true;
}

// ------------------------------------------------------------------------ rules

interface Rule {
  id: string;
  pattern: RegExp;
  message: string;
  applies: (p: P) => boolean;
}

const RULES: Rule[] = [
  {
    id: "RULE 12 (Angular)",
    pattern: /:[^;{}]*?(?<![\w.-])\d+(?:\.\d+)?px\b/,
    message:
      "raw px in a feature stylesheet.\n" +
      "  Colour, type, shape and elevation are Material's system tokens: use\n" +
      "  var(--mat-sys-*), set by the theme in src/styles/_theme.scss. Spacing is\n" +
      "  var(--app-space-*) from src/styles/_tokens.scss. Never a literal px value.",
    applies: isFeatureScss,
  },
  {
    id: "RULE 22e (Language)",
    pattern: /[\u064b-\u0652\u0670]/,
    message:
      "tashkeel in Arabic a user reads.\n" +
      "  No diacritic in any ar.json value or seeded _ar column. A word that needs\n" +
      "  a vowel mark to be read is the wrong word - replace it, do not strip the\n" +
      "  mark. See .claude/docs/language.md.",
    applies: isUserFacingArabic,
  },
  {
    id: "RULE 10 (Angular)",
    pattern: /\bsetTimeout\s*\(/,
    message:
      "setTimeout is not allowed.\n" +
      "  Model the timing in state with signals, or let CSS express the delay.",
    applies: isFrontendTs,
  },
  {
    id: "RULE 9 (Angular)",
    pattern: /(?:\bwindow\s*\.\s*)?\b(?:confirm|alert|prompt)\s*\(/,
    message:
      "native browser dialog.\n" +
      "  Ask with MatDialog for confirm(), report with MatSnackBar or a role=\"alert\"\n" +
      "  message in the page for alert(), and collect with a mat-form-field for prompt().",
    applies: isFrontendTs,
  },
  {
    id: "RULE 9 (Angular)",
    pattern: /<dialog[\s>]|<select[\s>]|<input[^>]*\btype\s*=\s*["'](?:radio|checkbox)["']/,
    message:
      "a native control Angular Material draws.\n" +
      "  Use MatDialog for <dialog>, mat-select for <select>, mat-radio-group for a\n" +
      "  radio and mat-checkbox or mat-slide-toggle for a checkbox.",
    applies: isFrontendTemplate,
  },
  {
    id: "RULE 14 (Django)",
    pattern: /\.objects\s*\./,
    message:
      "ORM access outside a repository.\n" +
      "  Every .objects. call belongs in apps/<feature>/repositories/.\n" +
      "  Views call services; services call repositories; repositories call the ORM.",
    applies: isDjangoAppPython,
  },
  {
    id: "RULE 14 (Django)",
    pattern: /\b(?:raw|extra)\s*\(\s*["']|\bcursor\s*\.\s*execute\s*\(/,
    message:
      "raw SQL in application code.\n" +
      "  Express it through the ORM. If that is genuinely impossible, put it in a\n" +
      "  repository method with a comment explaining why, and have db_engineer\n" +
      "  sign off with benchmark numbers.",
    applies: isDjangoAppPython,
  },
  {
    id: "RULE 16 (Django)",
    pattern: /\.hard_delete\s*\(|\bqueryset\s*\.\s*delete\s*\(\s*\)/,
    message:
      "hard delete.\n" +
      "  delete() must set deleted_at. Removing rows for real is a data migration,\n" +
      "  never an application action.",
    applies: isDjangoAppPython,
  },
];

const COMMENT_PREFIXES = ["//", "#", "*", "/*", "<!--"];

type Violation = { line: number; rule: Rule; text: string };

function scan(text: string, p: P): Violation[] {
  const out: Violation[] = [];
  const lines = text.split("\n");
  for (const rule of RULES) {
    if (!rule.applies(p)) continue;
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const stripped = line.trim();
      if (!stripped) continue;
      if (COMMENT_PREFIXES.some((c) => stripped.startsWith(c))) continue;
      if (rule.pattern.test(line)) {
        out.push({ line: i + 1, rule, text: stripped });
      }
    }
  }
  return out;
}

// ------------------------------------------------------------- edit result

function resultingText(tool: string, args: any, directory: string): { text: string; absPath: string } | null {
  const raw: string | undefined = args?.filePath ?? args?.file_path;
  if (!raw) return null;
  const absPath = isAbsolute(raw) ? raw : join(directory, raw);

  if (tool === "write") {
    return { text: String(args.content ?? ""), absPath };
  }

  if (tool === "edit") {
    let current = "";
    try {
      current = existsSync(absPath) ? readFileSync(absPath, "utf-8") : "";
    } catch {
      current = "";
    }
    const oldString: string = args.oldString ?? "";
    const newString: string = args.newString ?? "";
    const replaceAll: boolean = !!args.replaceAll;
    let text: string;
    if (replaceAll) {
      text = current.split(oldString).join(newString);
    } else {
      const idx = current.indexOf(oldString);
      if (idx === -1) {
        text = current;
      } else {
        text = current.slice(0, idx) + newString + current.slice(idx + oldString.length);
      }
    }
    return { text, absPath };
  }

  return null;
}

function blockMessage(absPath: string, violations: Violation[]): Error {
  const short = parsePath(absPath).base;
  const lines = violations.map(
    (v) => `${v.rule.id}: ${v.message}\n  ${absPath}:${v.line}\n    ${v.text}`,
  );
  return new Error(
    `Blocked: ${violations.length} rule violation(s) in ${short}.\n\n${lines.join("\n\n")}\n\nSee .claude/docs/design-pattern.md. Fix these before continuing.`,
  );
}

// ---------------------------------------------------------------------- plugin

export const Guards: Plugin = async ({ directory }) => {
  return {
    "tool.execute.before": async (input, output) => {
      const tool = input.tool;
      if (tool !== "edit" && tool !== "write") return;
      const result = resultingText(tool, output.args, directory);
      if (!result) return;
      const violations = scan(result.text, toP(result.absPath));
      if (violations.length > 0) {
        throw blockMessage(result.absPath, violations);
      }
    },
  };
};

export default Guards;
