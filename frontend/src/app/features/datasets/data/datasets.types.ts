export type DatasetStatus = 'queued' | 'importing' | 'ready' | 'failed' | 'cancelled';

export type DatasetSource = 'hub' | 'upload';

export type DatasetFormat = 'messages' | 'sharegpt' | 'instruction' | 'prompt_completion' | 'text' | 'unsupported';

export type MessageRole = 'system' | 'user' | 'assistant';

export type ColumnRole = 'prompt' | 'reply' | 'thinking';

export interface Mapping {
  readonly format: DatasetFormat;
  readonly conversation: string;
  readonly system: string;
  readonly prompt: string;
  readonly input: string;
  readonly reply: string;
  readonly thinking: string;
  readonly text: string;
}

export interface Message {
  readonly role: MessageRole;
  readonly content: string;
  readonly thinking: string;
}

export interface Conversation {
  readonly index: number;
  readonly messages: readonly Message[];
  readonly text: string;
}

export interface Dataset {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly source: DatasetSource;
  readonly repo_id: string;
  readonly config_name: string;
  readonly split: string;
  readonly file_name: string;
  readonly format: DatasetFormat | '';
  readonly mapping: Mapping | null;
  readonly row_limit: number | null;
  readonly source_rows: number | null;
  readonly status: DatasetStatus;
  readonly error_code: string;
  readonly rows: number;
  readonly skipped: number;
  readonly size_bytes: number;
  readonly sha256: string;
  readonly has_thinking: boolean;
  readonly excerpt: string;
  readonly created_by: string;
  readonly created_at: string;
}

export interface HubDataset {
  readonly repo_id: string;
  readonly downloads: number;
  readonly likes: number;
  readonly license: string;
  readonly gated: boolean;
  readonly size_category: string;
  readonly languages: readonly string[];
  readonly description: string;
  readonly in_library: boolean;
}

export interface HubSplit {
  readonly name: string;
  readonly rows: number | null;
}

export interface HubConfig {
  readonly name: string;
  readonly splits: readonly HubSplit[];
}

export interface Inspection extends HubDataset {
  readonly configs: readonly HubConfig[];
  readonly config: string;
  readonly split: string;
  readonly columns: readonly string[];
  readonly detected: DatasetFormat;
  readonly mapping: Mapping;
  readonly conversations: readonly Conversation[];
  readonly sample_rows: number;
  readonly sample_skipped: number;
}

export interface ChosenColumns {
  readonly prompt: string;
  readonly reply: string;
  readonly thinking: string;
}

export interface InspectQuery {
  readonly repo: string;
  readonly config?: string;
  readonly split?: string;
  readonly columns?: ChosenColumns;
}

export interface NewImport {
  readonly repo_id: string;
  readonly config: string;
  readonly split: string;
  readonly row_limit: number;
  readonly mapping: Mapping;
}

export interface DatasetChanges {
  readonly name: string;
  readonly description: string;
}

export interface InspectDialogData {
  readonly repo: string;
}

export interface EditDialogData {
  readonly dataset: Dataset;
}

export interface SizeRange {
  readonly key: 'under' | 'between' | 'over';
  readonly min: string;
  readonly max: string;
}

export const ACTIVE_STATUSES: readonly DatasetStatus[] = ['queued', 'importing'];

export const IMPORT_FAILURES: readonly string[] = [
  'gated',
  'not_found',
  'hf_unreachable',
  'unsupported_format',
  'disk_full',
];

export const LAYOUTS: readonly DatasetFormat[] = ['messages', 'sharegpt', 'instruction', 'prompt_completion', 'text'];

export const COLUMN_ROLES: readonly ColumnRole[] = ['prompt', 'reply', 'thinking'];

export const FORMAT_ICONS: Readonly<Record<DatasetFormat, string>> = {
  messages: 'fa-comments',
  sharegpt: 'fa-comments',
  instruction: 'fa-list-check',
  prompt_completion: 'fa-reply',
  text: 'fa-align-left',
  unsupported: 'fa-circle-question',
};

export const DEFAULT_ROW_LIMIT = 10_000;

export const MAX_ROW_LIMIT = 1_000_000;

export const MAX_UPLOAD_BYTES = 200 * 1024 * 1024;

export const UPLOAD_TYPES = '.jsonl,.json,.csv';
