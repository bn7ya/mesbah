/**
 * Helpers for hybrid-reasoning `<think>…</think>` blocks (thinking models,
 * e.g. Qwen3). Mirrors backend `app/core/think.py` — keep the two in sync.
 */

export interface ThinkParts {
  /** The chain-of-thought text; `null` when the reply has no think block (answer model). */
  thinking: string | null;
  answer: string;
  /** `false` while a streamed reply is still inside an unclosed `<think>`. */
  closed: boolean;
}

export function splitThink(content: string): ThinkParts {
  if (!content) return { thinking: null, answer: content, closed: true };
  const m = /<think>([\s\S]*?)<\/think>/i.exec(content);
  if (m) {
    const answer = (content.slice(0, m.index) + content.slice(m.index + m[0].length)).trim();
    return { thinking: m[1].trim(), answer, closed: true };
  }
  const open = content.toLowerCase().indexOf('<think>');
  if (open >= 0) {
    return { thinking: content.slice(open + '<think>'.length).trim(), answer: content.slice(0, open).trim(), closed: false };
  }
  return { thinking: null, answer: content, closed: true };
}

/** Recombine a thinking chain and an answer in the format thinking models emit. */
export function joinThink(thinking: string, answer: string): string {
  return `<think>\n${thinking}\n</think>\n\n${answer}`;
}
