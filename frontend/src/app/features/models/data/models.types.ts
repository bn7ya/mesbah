export type ModelStatus = 'queued' | 'downloading' | 'ready' | 'failed' | 'cancelled';

export type ModelFamily = 'dense_decoder' | 'moe_decoder' | 'encoder_decoder' | 'other';

export type FitVerdict = 'fits' | 'tight' | 'too_large' | 'cpu_only' | 'unknown';

export type FitUse = 'chat' | 'chat_full' | 'training';

export type HubTask = 'text-generation' | 'text2text-generation';

export interface Fit {
  readonly verdict: FitVerdict;
  readonly required_bytes: number | null;
  readonly available_bytes: number;
}

export type FitSet = Readonly<Record<FitUse, Fit>>;

export interface LibraryRef {
  readonly id: string;
  readonly status: ModelStatus;
}

export interface HubResult {
  readonly repo_id: string;
  readonly downloads: number;
  readonly likes: number;
  readonly pipeline_tag: string;
  readonly parameters: number | null;
  readonly license: string;
  readonly gated: boolean;
  readonly model_type: string;
  readonly supports_thinking: boolean;
  readonly fit: FitSet;
  readonly in_library: LibraryRef | null;
}

export interface Architecture {
  readonly family: ModelFamily;
  readonly model_type: string;
  readonly layers: number | null;
  readonly hidden_size: number | null;
  readonly heads: number | null;
  readonly kv_heads: number | null;
  readonly vocab_size: number | null;
  readonly context_length: number | null;
  readonly experts: number | null;
  readonly experts_per_token: number | null;
  readonly expert_size: number | null;
}

export interface Inspection extends HubResult {
  readonly revision: string;
  readonly family: ModelFamily;
  readonly architecture: Architecture;
  readonly active_parameters: number | null;
  readonly has_chat_template: boolean;
  readonly downloadable: boolean;
  readonly size_bytes: number;
}

export interface LibraryModel {
  readonly id: string;
  readonly repo_id: string;
  readonly revision: string;
  readonly family: ModelFamily;
  readonly model_type: string;
  readonly architecture: Architecture;
  readonly parameters: number | null;
  readonly active_parameters: number | null;
  readonly license: string;
  readonly gated: boolean;
  readonly supports_thinking: boolean;
  readonly has_chat_template: boolean;
  readonly size_bytes: number;
  readonly downloaded_bytes: number;
  readonly status: ModelStatus;
  readonly error_code: string;
  readonly downloaded_at: string | null;
  readonly created_at: string;
  readonly fit: FitSet;
}

export interface HubQuery {
  readonly search: string;
  readonly task: HubTask;
}

export interface NewModel {
  readonly repo_id: string;
}

export interface InspectionDialogData {
  readonly repo: string;
}

export const ACTIVE_STATUSES: readonly ModelStatus[] = ['queued', 'downloading'];

export const HUB_TASKS: readonly HubTask[] = ['text-generation', 'text2text-generation'];

export const FIT_USES: readonly FitUse[] = ['chat', 'chat_full', 'training'];

export const DOWNLOAD_FAILURES: readonly string[] = ['gated', 'not_found', 'disk_full', 'network'];

export const POPULAR: HubQuery = { search: '', task: 'text-generation' };

export const FIT_ICONS: Readonly<Record<FitVerdict, string>> = {
  fits: 'fa-circle-check',
  tight: 'fa-triangle-exclamation',
  too_large: 'fa-circle-xmark',
  cpu_only: 'fa-microchip',
  unknown: 'fa-circle-question',
};
