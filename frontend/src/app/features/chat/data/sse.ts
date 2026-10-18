import type { Message, ParsedFrames, ReplyEvent, SseFrame } from './chat.types';

const BOUNDARY = /\r\n\r\n|\n\n|\r\r/g;
const LINE_BREAK = /\r\n|\r|\n/;

export function parseFrames(text: string, from: number): ParsedFrames {
  const frames: SseFrame[] = [];
  const boundary = new RegExp(BOUNDARY.source, 'g');
  boundary.lastIndex = from;
  let start = from;
  for (let match = boundary.exec(text); match !== null; match = boundary.exec(text)) {
    const frame = readFrame(text.slice(start, match.index));
    if (frame !== null) {
      frames.push(frame);
    }
    start = match.index + match[0].length;
  }
  return { frames, next: start };
}

function readFrame(block: string): SseFrame | null {
  let event = 'message';
  const data: string[] = [];
  for (const line of block.split(LINE_BREAK)) {
    if (line === '' || line.startsWith(':')) {
      continue;
    }
    const colon = line.indexOf(':');
    const field = colon === -1 ? line : line.slice(0, colon);
    const raw = colon === -1 ? '' : line.slice(colon + 1);
    const value = raw.startsWith(' ') ? raw.slice(1) : raw;
    if (field === 'event') {
      event = value;
    } else if (field === 'data') {
      data.push(value);
    }
  }
  return data.length === 0 ? null : { event, data: data.join('\n') };
}

export function toReplyEvent(frame: SseFrame): ReplyEvent | null {
  const payload = readJson(frame.data);
  if (payload === null) {
    return null;
  }
  switch (frame.event) {
    case 'start':
      return isMessage(payload['asked']) && isMessage(payload['reply'])
        ? { kind: 'start', asked: payload['asked'], reply: payload['reply'] }
        : null;
    case 'ready':
      return typeof payload['engine'] === 'string' ? { kind: 'ready', engine: payload['engine'] } : null;
    case 'thinking':
    case 'content':
      return typeof payload['text'] === 'string' ? { kind: frame.event, text: payload['text'] } : null;
    case 'done':
      return isMessage(payload['reply']) ? { kind: 'done', reply: payload['reply'] } : null;
    case 'error':
      return typeof payload['code'] === 'string' && isMessage(payload['reply'])
        ? {
            kind: 'error',
            code: payload['code'],
            message: typeof payload['message'] === 'string' ? payload['message'] : '',
            reply: payload['reply'],
          }
        : null;
    default:
      return null;
  }
}

function readJson(data: string): Readonly<Record<string, unknown>> | null {
  try {
    const value: unknown = JSON.parse(data);
    return typeof value === 'object' && value !== null && !Array.isArray(value)
      ? (value as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

function isMessage(value: unknown): value is Message {
  return typeof value === 'object' && value !== null && typeof (value as { id?: unknown }).id === 'string';
}
