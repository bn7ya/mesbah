/**
 * Port of the `.claude` session-awareness hooks for opencode (rule 28).
 *
 * Claude Code runs six hooks around a session; opencode has none of those
 * events, so this plugin drives the same Python hooks and surfaces their
 * output through the two channels opencode offers:
 *
 *   - a synthetic part on `chat.message`  -> prompt-level context (git-flow,
 *     session-start, session-peers) that the model actually reads;
 *   - a TUI toast on `tool.execute.before`-> tool-level warnings (file
 *     conflict, shared-resource contention) that never block the work.
 *
 * The one thing opencode does not do for itself is anchor liveness. Claude
 * Code's harness writes `~/.claude/sessions/<pid>.json`; every peer-lookup
 * trusts that document because its `procStart` is checked against a real
 * `/proc` entry. So the plugin registers this session (its own pid) before
 * anything else, after which `peers`, `holders`, `reap` and file-conflict all
 * find it exactly as they would a Claude session.
 *
 * `memory-sync` is the one hook that becomes an *action* rather than a notice:
 * opencode has no "block the stop", so a stale feature CLAUDE.md is answered
 * by re-prompting the session to finish the work it left behind.
 */

import type { Plugin } from "@opencode-ai/plugin";
import { spawn } from "node:child_process";
import { appendFileSync, existsSync } from "node:fs";
import { basename, isAbsolute, join, resolve } from "node:path";
import { randomUUID } from "node:crypto";

const HOOKS_REL = join(".claude", "hooks");
const HOOK_TIMEOUT_MS = 10_000;
const WRITE_TOOLS = new Set(["edit", "write"]);
const SHELL_TOOLS = new Set(["bash", "shell"]);
const FEATURE_ROOTS: ReadonlyArray<ReadonlyArray<string>> = [
  ["frontend", "src", "app", "features"],
  ["backend", "apps"],
];
const IGNORED_APPS = new Set(["common"]);
const MAX_MEMORY_SYNC_PER_SESSION = 3;

function runHook(hooksDir: string, file: string, event: Record<string, unknown>): Promise<string> {
  return new Promise((resolvePromise) => {
    let settled = false;
    const finish = (value: string) => {
      if (!settled) {
        settled = true;
        resolvePromise(value);
      }
    };
    let child;
    try {
      child = spawn("python3", [join(hooksDir, file)], { stdio: ["pipe", "pipe", "pipe"] });
    } catch {
      finish("");
      return;
    }
    let stdout = "";
    let timer = setTimeout(() => {
      try {
        child.kill("SIGKILL");
      } catch {
        /* already gone */
      }
      finish("");
    }, HOOK_TIMEOUT_MS);
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
    });
    child.on("close", () => {
      clearTimeout(timer);
      finish(stdout);
    });
    child.on("error", () => {
      clearTimeout(timer);
      finish("");
    });
    try {
      child.stdin?.end(JSON.stringify(event));
    } catch {
      clearTimeout(timer);
      finish("");
    }
  });
}

function extractMessage(stdout: string): string {
  const trimmed = stdout.trim();
  if (!trimmed) return "";
  try {
    const parsed = JSON.parse(trimmed);
    return parsed?.hookSpecificOutput?.additionalContext || parsed?.systemMessage || "";
  } catch {
    return trimmed;
  }
}

// The feature directory a path belongs to, mirroring memory-sync.py.
function featureDirFor(absPath: string, root: string): string | null {
  const base = root.endsWith("/") ? root : root + "/";
  if (!absPath.startsWith(base)) return null;
  const rel = absPath.slice(base.length).replace(/^\//, "");
  const parts = rel.split("/").filter(Boolean);
  for (const marker of FEATURE_ROOTS) {
    const n = marker.length;
    if (parts.length > n + 1 && marker.every((seg, i) => parts[i] === seg)) {
      const name = parts[n];
      if (IGNORED_APPS.has(name)) return null;
      const feature = join(root, ...marker, name);
      return existsSync(feature) ? feature : null;
    }
  }
  return null;
}

type FeatureMap = Map<string, boolean>; // feature -> has its CLAUDE.md been written this session

export const Sessions: Plugin = async ({ client, directory, worktree }) => {
  const cwd = directory;
  const projectRoot = worktree || directory;
  const hooksDir = join(projectRoot, HOOKS_REL);
  const selfName = `opencode-${process.pid}`;

  const registered = new Set<string>();
  const sessionStarted = new Set<string>();
  const issuedContinuations = new Set<string>();
  const featureTouched = new Map<string, FeatureMap>();
  const memorySyncCount = new Map<string, number>();

  const ensureRegistered = async (sessionID: string) => {
    if (!sessionID || registered.has(sessionID)) return;
    registered.add(sessionID);
    await runHook(hooksDir, "register-session.py", {
      session_id: sessionID,
      pid: process.pid,
      cwd: projectRoot,
      name: selfName,
    });
  };

  const logPrompt = (sessionID: string, prompt: string) => {
    const text = prompt.trim();
    if (!text) return;
    const stamp = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
    const entry = `[${stamp}] session=${sessionID.slice(0, 8)}\n${text}\n\n---\n\n`;
    try {
      appendFileSync(join(projectRoot, "prompt.txt"), entry, "utf-8");
    } catch {
      /* logging never blocks a prompt */
    }
  };

  const toast = (title: string, message: string) => {
    try {
      void client.tui.showToast({ body: { title, message, variant: "warning" } });
    } catch {
      /* a toast is a courtesy, not a contract */
    }
  };

  const memorySyncMessage = (stale: Array<[string, string]>) => {
    const lines = [
      "Feature memory is out of sync (rule 3 in CLAUDE.md).",
      "",
      "You changed these features but their CLAUDE.md was not written:",
      "",
    ];
    for (const [feature, why] of stale) {
      const rel = feature.startsWith(projectRoot) ? feature.slice(projectRoot.length).replace(/^\//, "") : feature;
      lines.push(`  - ${rel}/CLAUDE.md  (${why})`);
    }
    lines.push(
      "",
      "Write or update each one, then finish. A feature's CLAUDE.md should record what the",
      "feature does, its slice counterpart on the other side, its routes and endpoints, and any",
      "decision a future session would otherwise re-litigate.",
    );
    return lines.join("\n");
  };

  const runMemorySync = async (sessionID: string) => {
    const touched = featureTouched.get(sessionID);
    if (!touched) return;
    const used = memorySyncCount.get(sessionID) ?? 0;
    if (used >= MAX_MEMORY_SYNC_PER_SESSION) return;
    const stale: Array<[string, string]> = [];
    for (const [feature, memoryWritten] of touched) {
      const memory = join(feature, "CLAUDE.md");
      if (!existsSync(memory)) stale.push([feature, "missing"]);
      else if (!memoryWritten) stale.push([feature, "not updated"]);
    }
    if (stale.length === 0) return;
    memorySyncCount.set(sessionID, used + 1);
    const text = memorySyncMessage(stale);
    issuedContinuations.add(text);
    try {
      await client.session.prompt({
        path: { id: sessionID },
        body: { parts: [{ type: "text", text }] },
      });
    } catch {
      /* a continuation that fails is no worse than the original stop */
    }
  };

  const recordEdit = (sessionID: string, args: any) => {
    const raw: string | undefined = args?.filePath ?? args?.file_path;
    if (!raw) return;
    const absPath = isAbsolute(raw) ? raw : resolve(cwd, raw);
    const feature = featureDirFor(absPath, projectRoot);
    if (!feature) return;
    const map = featureTouched.get(sessionID) ?? new Map();
    const was = map.get(feature) ?? false;
    map.set(feature, was || basename(absPath) === "CLAUDE.md");
    featureTouched.set(sessionID, map);
  };

  const cleanup = (sessionID: string) => {
    registered.delete(sessionID);
    sessionStarted.delete(sessionID);
    featureTouched.delete(sessionID);
    memorySyncCount.delete(sessionID);
  };

  return {
    "chat.message": async (input, output) => {
      const sessionID = input.sessionID;
      const parts = output.parts as Array<{ type: string; text?: string; id?: string; messageID?: string; sessionID?: string }>;
      const prompt = (parts.find((p) => p.type === "text")?.text ?? "").toString();
      const messageID = (output as any).message?.id;

      // A continuation I issued is not a user prompt: no logging, no hooks,
      // no re-injection. input.messageID is undefined here, so match on text.
      if (issuedContinuations.has(prompt.trim())) return;

      await ensureRegistered(sessionID);
      logPrompt(sessionID, prompt);

      const blocks: string[] = [];
      if (!sessionStarted.has(sessionID)) {
        sessionStarted.add(sessionID);
        const started = await runHook(hooksDir, "session-start.py", {
          session_id: sessionID,
          cwd: projectRoot,
          prompt,
          hook_event_name: "SessionStart",
        });
        if (started.trim()) blocks.push(started.trim());
      }

      const peers = await runHook(hooksDir, "session-peers.py", {
        session_id: sessionID,
        cwd: projectRoot,
        prompt,
        hook_event_name: "UserPromptSubmit",
      });
      if (peers.trim()) blocks.push(peers.trim());

      const gate = await runHook(hooksDir, "git-flow-gate.py", { prompt, session_id: sessionID });
      if (gate.trim()) blocks.push(gate.trim());

      if (blocks.length > 0 && messageID) {
        const text = blocks.join("\n\n");
        parts.push({
          id: `prt_sessions_${randomUUID()}`,
          sessionID,
          messageID,
          type: "text",
          synthetic: true,
          text,
        });
      }
    },

    "tool.execute.before": async (input, output) => {
      const { tool, sessionID, callID } = input;
      const args = output.args as any;
      if (WRITE_TOOLS.has(tool)) {
        const raw: string | undefined = args?.filePath ?? args?.file_path;
        if (!raw) return;
        const absPath = isAbsolute(raw) ? raw : resolve(cwd, raw);
        const msg = extractMessage(
          await runHook(hooksDir, "file-conflict-warn.py", {
            session_id: sessionID,
            cwd: projectRoot,
            tool_input: { file_path: absPath },
            hook_event_name: "PreToolUse",
          })
        );
        if (msg) toast("File conflict", `${selfName} may be editing ${basename(absPath)} in another session.\n\n${msg}`);
      } else if (SHELL_TOOLS.has(tool)) {
        const command: string = args?.command ?? "";
        if (!command) return;
        const msg = extractMessage(
          await runHook(hooksDir, "resource-claim.py", {
            session_id: sessionID,
            tool_use_id: callID,
            cwd: projectRoot,
            tool_input: { command },
            hook_event_name: "PreToolUse",
          })
        );
        if (msg) toast("Shared resource in use", msg);
      }
    },

    "tool.execute.after": async (input) => {
      const { tool, sessionID, callID } = input;
      const args = input.args as any;
      if (WRITE_TOOLS.has(tool)) {
        recordEdit(sessionID, args);
        const raw: string | undefined = args?.filePath ?? args?.file_path;
        if (!raw) return;
        const absPath = isAbsolute(raw) ? raw : resolve(cwd, raw);
        await runHook(hooksDir, "touch-file.py", {
          session_id: sessionID,
          cwd: projectRoot,
          tool_input: { file_path: absPath },
        });
      } else if (SHELL_TOOLS.has(tool)) {
        // Releasing is unconditional: a muted session still lets go.
        await runHook(hooksDir, "resource-claim.py", {
          session_id: sessionID,
          tool_use_id: callID,
          cwd: projectRoot,
          hook_event_name: "PostToolUse",
        });
      }
    },

    event: async ({ event }) => {
      const ev = event as { type: string; properties?: { sessionID?: string; info?: { id?: string } } };
      const sessionID = ev.properties?.sessionID ?? ev.properties?.info?.id;
      if (ev.type === "session.created" && sessionID) {
        await ensureRegistered(sessionID);
      } else if (ev.type === "session.idle" && sessionID) {
        await runMemorySync(sessionID);
      } else if (ev.type === "session.deleted" && sessionID) {
        cleanup(sessionID);
      }
    },
  };
};

export default Sessions;
