import type { ApiError } from '@core/http/api.types';

export type MessageRole = 'user' | 'assistant' | 'system';

export type MessageStatus = 'streaming' | 'complete' | 'stopped' | 'failed';

export type MessagePart = 'content' | 'thinking';

export interface NamedRef {
  readonly id: string;
  readonly name: string;
}

export interface ReplySettings {
  readonly temperature?: number;
  readonly top_p?: number;
  readonly max_tokens?: number;
}

export type FullReplySettings = Required<ReplySettings>;

export type ReplySettingKey = keyof FullReplySettings;

export interface Conversation {
  readonly id: string;
  readonly project: string;
  readonly title: string;
  readonly version: NamedRef | null;
  readonly engine: NamedRef | null;
  readonly system_prompt: string;
  readonly thinking: boolean;
  readonly generation: ReplySettings;
  readonly message_count: number | null;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface NewConversation {
  readonly project: string;
  readonly title?: string;
  readonly version?: string | null;
  readonly thinking?: boolean;
}

export interface ConversationChange {
  readonly title?: string;
  readonly version?: string | null;
  readonly engine?: string | null;
  readonly system_prompt?: string;
  readonly thinking?: boolean;
  readonly generation?: ReplySettings;
}

export interface Message {
  readonly id: string;
  readonly position: number;
  readonly role: MessageRole;
  readonly status: MessageStatus;
  readonly content: string;
  readonly thinking: string;
  readonly version: NamedRef | null;
  readonly engine_name: string;
  readonly finish_reason: string;
  readonly error_code: string;
  readonly tokens_prompt: number | null;
  readonly tokens_completion: number | null;
  readonly latency_ms: number | null;
  readonly original_content: string | null;
  readonly original_thinking: string | null;
  readonly content_edited_at: string | null;
  readonly thinking_edited_at: string | null;
  readonly edited_by: string | null;
  readonly approved: boolean;
  readonly approved_by: string | null;
  readonly include_in_training: boolean;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface MessageEdit {
  readonly seen: string;
  readonly content?: string;
  readonly thinking?: string;
  readonly include_in_training?: boolean;
}

export interface MessageChange {
  readonly content?: string;
  readonly thinking?: string;
  readonly include_in_training?: boolean;
}

export interface ProjectDefaults {
  readonly system_prompt: string;
  readonly thinking: boolean;
  readonly generation: FullReplySettings;
}

export interface VersionOption {
  readonly id: string;
  readonly number: number;
  readonly name: string;
  readonly is_active: boolean;
}

export interface EngineOption {
  readonly id: string;
  readonly name: string;
  readonly enabled: boolean;
  readonly is_default: boolean;
}

export interface SseFrame {
  readonly event: string;
  readonly data: string;
}

export interface ParsedFrames {
  readonly frames: readonly SseFrame[];
  readonly next: number;
}

export type ReplyEvent =
  | { readonly kind: 'start'; readonly asked: Message; readonly reply: Message }
  | { readonly kind: 'ready'; readonly engine: string }
  | { readonly kind: 'thinking'; readonly text: string }
  | { readonly kind: 'content'; readonly text: string }
  | { readonly kind: 'done'; readonly reply: Message }
  | { readonly kind: 'error'; readonly code: string; readonly message: string; readonly reply: Message };

export type StreamPhase = 'loading' | 'thinking' | 'writing';

export interface StreamState {
  readonly replyId: string;
  readonly phase: StreamPhase;
  readonly thinking: string;
  readonly content: string;
  readonly engine: string;
}

export interface ThinkingOpenSource {
  readonly streaming: boolean;
  readonly editing: boolean;
}

export interface PinSource {
  readonly id: string | null;
  readonly started: boolean;
}

export type CreateConversationResult =
  | { readonly conversation: Conversation }
  | { readonly error: ApiError };

export interface SettingRange {
  readonly min: number;
  readonly max: number;
  readonly step: number;
}

export interface ReplySetting {
  readonly key: ReplySettingKey;
  readonly labelKey: string;
  readonly hintKey: string;
  readonly termKey: string;
  readonly range: SettingRange;
  readonly digits: number;
}

export const FOLLOW_ACTIVE = 'active';

export const DEFAULT_ENGINE = 'default';

export const PAGE_SIZE = 200;

export const CONVERSATIONS_PAGE_SIZE = 30;

export const TITLE_MAX = 200;

export const PROMPT_MAX = 20000;

export const MESSAGE_MAX = 100_000;

export const ENGINES_PAGE_SIZE = 50;

export const SETTLE_ATTEMPTS = 10;

export const SETTLE_DELAY_MS = 400;

export const REPLY_SETTINGS: readonly ReplySetting[] = [
  {
    key: 'temperature',
    labelKey: 'chat.settings.temperature',
    hintKey: 'chat.settings.temperatureHint',
    termKey: 'temperature',
    range: { min: 0, max: 2, step: 0.05 },
    digits: 2,
  },
  {
    key: 'top_p',
    labelKey: 'chat.settings.topP',
    hintKey: 'chat.settings.topPHint',
    termKey: 'top_p',
    range: { min: 0, max: 1, step: 0.05 },
    digits: 2,
  },
  {
    key: 'max_tokens',
    labelKey: 'chat.settings.maxTokens',
    hintKey: 'chat.settings.maxTokensHint',
    termKey: 'token',
    range: { min: 16, max: 32768, step: 16 },
    digits: 0,
  },
];
