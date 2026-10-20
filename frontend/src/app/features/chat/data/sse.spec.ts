import { describe, expect, it } from 'vitest';

import type { Message } from './chat.types';
import { parseFrames, toReplyEvent } from './sse';

function message(id: string, overrides: Partial<Message> = {}): Message {
  return {
    id,
    position: 0,
    role: 'assistant',
    status: 'complete',
    content: '',
    thinking: '',
    version: null,
    engine_name: '',
    finish_reason: '',
    error_code: '',
    tokens_prompt: null,
    tokens_completion: null,
    latency_ms: null,
    original_content: null,
    original_thinking: null,
    content_edited_at: null,
    thinking_edited_at: null,
    edited_by: null,
    approved: false,
    approved_by: null,
    include_in_training: true,
    created_at: '2026-10-18T10:00:00Z',
    updated_at: '2026-10-18T10:00:00Z',
    ...overrides,
  };
}

describe('parseFrames', () => {
  it('reads one whole event', () => {
    const text = 'event: content\ndata: {"text": "Hello"}\n\n';

    const { frames, next } = parseFrames(text, 0);

    expect(frames).toEqual([{ event: 'content', data: '{"text": "Hello"}' }]);
    expect(next).toBe(text.length);
  });

  it('reads several events in one chunk, in order', () => {
    const text = 'event: ready\ndata: {"engine": "Mesbah"}\n\nevent: content\ndata: {"text": "a"}\n\n';

    expect(parseFrames(text, 0).frames.map((frame) => frame.event)).toEqual(['ready', 'content']);
  });

  it('keeps an event that has not finished until the rest arrives', () => {
    const first = 'event: content\ndata: {"text": "Hel';
    const early = parseFrames(first, 0);

    expect(early.frames).toEqual([]);
    expect(early.next).toBe(0);

    const second = `${first}lo"}\n\nevent: content\ndata: {"te`;
    const later = parseFrames(second, early.next);

    expect(later.frames).toEqual([{ event: 'content', data: '{"text": "Hello"}' }]);
    expect(second.slice(later.next)).toBe('event: content\ndata: {"te');
  });

  it('does not read an event twice when it is handed the whole text again', () => {
    const one = 'event: content\ndata: {"text": "a"}\n\n';
    const first = parseFrames(one, 0);
    const text = `${one}event: content\ndata: {"text": "b"}\n\n`;

    const second = parseFrames(text, first.next);

    expect(second.frames).toEqual([{ event: 'content', data: '{"text": "b"}' }]);
  });

  it('waits when a chunk ends between the two line breaks', () => {
    const half = 'event: content\ndata: {"text": "a"}\n';

    expect(parseFrames(half, 0).frames).toEqual([]);
    expect(parseFrames(`${half}\n`, 0).frames).toHaveLength(1);
  });

  it('skips a keepalive comment', () => {
    const text = ': keepalive\n\nevent: content\ndata: {"text": "a"}\n\n';

    const { frames, next } = parseFrames(text, 0);

    expect(frames).toEqual([{ event: 'content', data: '{"text": "a"}' }]);
    expect(next).toBe(text.length);
  });

  it('skips a comment inside an event', () => {
    const text = 'event: content\n: still here\ndata: {"text": "a"}\n\n';

    expect(parseFrames(text, 0).frames).toEqual([{ event: 'content', data: '{"text": "a"}' }]);
  });

  it('joins the lines of a multi-line data field with a line break', () => {
    const text = 'event: content\ndata: first\ndata: second\n\n';

    expect(parseFrames(text, 0).frames).toEqual([{ event: 'content', data: 'first\nsecond' }]);
  });

  it('reads carriage-return line endings', () => {
    const text = 'event: content\r\ndata: {"text": "a"}\r\n\r\n';

    expect(parseFrames(text, 0).frames).toEqual([{ event: 'content', data: '{"text": "a"}' }]);
  });

  it('names an event without a name "message" and drops one without data', () => {
    const text = 'data: plain\n\nevent: empty\n\n';

    expect(parseFrames(text, 0).frames).toEqual([{ event: 'message', data: 'plain' }]);
  });

  it('keeps the value after the first colon whole, and strips one leading space only', () => {
    const text = 'event: content\ndata:  two: spaces\n\n';

    expect(parseFrames(text, 0).frames).toEqual([{ event: 'content', data: ' two: spaces' }]);
  });

  it('reads text in any script', () => {
    const text = 'event: content\ndata: {"text": "مرحبا 你好"}\n\n';

    expect(parseFrames(text, 0).frames[0].data).toContain('مرحبا');
  });
});

describe('toReplyEvent', () => {
  it('reads the two saved messages from start', () => {
    const asked = message('a', { role: 'user' });
    const reply = message('r', { status: 'streaming' });

    const event = toReplyEvent({ event: 'start', data: JSON.stringify({ asked, reply }) });

    expect(event).toEqual({ kind: 'start', asked, reply });
  });

  it('reads the engine from ready', () => {
    expect(toReplyEvent({ event: 'ready', data: '{"engine": "Mesbah"}' })).toEqual({ kind: 'ready', engine: 'Mesbah' });
  });

  it('reads the text of thinking and content', () => {
    expect(toReplyEvent({ event: 'thinking', data: '{"text": "hm"}' })).toEqual({ kind: 'thinking', text: 'hm' });
    expect(toReplyEvent({ event: 'content', data: '{"text": "Hi"}' })).toEqual({ kind: 'content', text: 'Hi' });
  });

  it('reads the saved reply from done', () => {
    const reply = message('r', { content: 'Hi' });

    expect(toReplyEvent({ event: 'done', data: JSON.stringify({ reply }) })).toEqual({ kind: 'done', reply });
  });

  it('reads the code, the message and the saved reply from error', () => {
    const reply = message('r', { status: 'failed', error_code: 'engine_unreachable' });

    const event = toReplyEvent({
      event: 'error',
      data: JSON.stringify({ code: 'engine_unreachable', message: 'The engine isn\'t running.', reply }),
    });

    expect(event).toEqual({ kind: 'error', code: 'engine_unreachable', message: 'The engine isn\'t running.', reply });
  });

  it('ignores an event it does not know, and data that is not JSON', () => {
    expect(toReplyEvent({ event: 'surprise', data: '{}' })).toBeNull();
    expect(toReplyEvent({ event: 'content', data: 'not json' })).toBeNull();
    expect(toReplyEvent({ event: 'content', data: '[]' })).toBeNull();
    expect(toReplyEvent({ event: 'content', data: '{"text": 3}' })).toBeNull();
  });
});
