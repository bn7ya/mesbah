import type { ApiError } from '@core/http/api.types';

export type Family = 'dense_decoder' | 'moe_decoder' | 'encoder_decoder';

export type FitVerdict = 'fits' | 'tight' | 'too_large' | 'cpu_only' | 'unknown';

export type Note = 'embeddings_dominate';

export type PartKey = 'embeddings' | 'attention' | 'feed_forward' | 'router' | 'norms' | 'lm_head';

export interface Design {
  readonly family: Family;
  readonly layers: number;
  readonly hidden_size: number;
  readonly heads: number;
  readonly kv_heads: number | null;
  readonly intermediate_size: number;
  readonly vocab_size: number;
  readonly context_length: number;
  readonly experts: number;
  readonly experts_per_token: number;
  readonly encoder_layers: number;
  readonly decoder_layers: number;
  readonly tie_embeddings: boolean;
}

export interface DesignRequest {
  readonly family: Family;
  readonly hidden_size: number | null;
  readonly heads: number | null;
  readonly intermediate_size: number | null;
  readonly vocab_size: number | null;
  readonly context_length: number | null;
  readonly tie_embeddings: boolean;
  readonly layers?: number | null;
  readonly kv_heads?: number | null;
  readonly experts?: number | null;
  readonly experts_per_token?: number | null;
  readonly encoder_layers?: number | null;
  readonly decoder_layers?: number | null;
}

export type Parts = Readonly<Record<PartKey, number>>;

export interface Counts {
  readonly total: number;
  readonly active: number;
  readonly embeddings_share: number;
  readonly parts: Parts;
}

export interface Fit {
  readonly verdict: FitVerdict;
  readonly required_bytes: number | null;
  readonly available_bytes: number;
}

export interface Memory {
  readonly precision: string;
  readonly weights_bytes: number;
  readonly adamw_bytes: number;
  readonly adamw_8bit_bytes: number;
  readonly activation_bytes: number;
  readonly training_bytes: number;
  readonly training_8bit_bytes: number;
  readonly fit: Fit;
  readonly fit_8bit: Fit;
}

export interface Estimate {
  readonly design: Design;
  readonly counts: Counts;
  readonly memory: Memory;
  readonly note: Note | null;
  readonly tokenizer_vocabulary: number | null;
}

export interface EstimateRequest {
  readonly design: DesignRequest;
  readonly seq_len: number;
  readonly batch: number;
  readonly tokenizer: string;
}

export interface RaisedVocabulary {
  readonly tokenizer: string;
  readonly tokens: number;
}

export interface PresetWire {
  readonly name: string;
  readonly design: Design;
  readonly counts: Counts;
}

export interface PresetListWire {
  readonly presets: readonly PresetWire[];
}

export interface DraftWire extends Estimate {
  readonly id: string;
  readonly name: string;
  readonly notes: string;
  readonly tokenizer: string;
  readonly seq_len: number;
  readonly batch: number;
  readonly created_at: string;
  readonly updated_at: string;
  readonly created_by: string | null;
}

export interface NewDraftWire {
  readonly name: string;
  readonly notes: string;
  readonly design: DesignRequest;
  readonly tokenizer: string;
  readonly seq_len?: number;
  readonly batch?: number;
}

export interface DraftChangeWire {
  readonly name?: string;
  readonly notes?: string;
  readonly design?: DesignRequest;
  readonly tokenizer?: string;
  readonly seq_len?: number;
  readonly batch?: number;
}

export interface DatasetChoice {
  readonly id: string;
  readonly max_rows: number | null;
}

export interface TrainRequest {
  readonly name: string;
  readonly corrections_from: readonly string[];
  readonly datasets: readonly DatasetChoice[];
}

export interface TrainStarted {
  readonly project: string;
  readonly run: string;
}

export const NUMBER_KEYS = [
  'layers',
  'encoder_layers',
  'decoder_layers',
  'hidden_size',
  'heads',
  'kv_heads',
  'intermediate_size',
  'experts',
  'experts_per_token',
  'vocab_size',
  'context_length',
  'seq_len',
  'batch',
] as const;

export type NumberKey = (typeof NUMBER_KEYS)[number];

export interface Blueprint extends Readonly<Record<NumberKey, number | null>> {
  readonly family: Family;
  readonly tie_embeddings: boolean;
  readonly tokenizer: string;
}

export interface Preset {
  readonly name: string;
  readonly family: Family;
  readonly blueprint: Blueprint;
  readonly counts: Counts;
}

export interface Draft {
  readonly id: string;
  readonly name: string;
  readonly notes: string;
  readonly family: Family;
  readonly blueprint: Blueprint;
  readonly counts: Counts;
  readonly updatedAt: string;
  readonly createdBy: string | null;
}

export interface DraftText {
  readonly name: string;
  readonly notes: string;
}

export interface SaveDialogData {
  readonly mode: 'save' | 'rename';
  readonly draft: Draft | null;
}

export interface TrainDialogData {
  readonly draft: Draft;
}

export interface ProjectRef {
  readonly id: string;
  readonly name: string;
}

export interface PlanWire {
  readonly corrections: number;
}

export interface Source extends ProjectRef {
  readonly corrections: number | null;
}

export interface DatasetWire {
  readonly id: string;
  readonly name: string;
  readonly status: string;
  readonly rows: number;
  readonly has_thinking: boolean;
}

export interface DatasetOption {
  readonly id: string;
  readonly name: string;
  readonly rows: number;
  readonly hasThinking: boolean;
}

export type EstimateOutcome =
  | { readonly kind: 'estimate'; readonly estimate: Estimate; readonly request: EstimateRequest }
  | { readonly kind: 'refusal'; readonly error: ApiError }
  | { readonly kind: 'blocked' };

export type SaveResult = { readonly draft: Draft } | { readonly error: ApiError };

export type TrainResult = { readonly started: TrainStarted } | { readonly error: ApiError };

export interface Limit {
  readonly min: number;
  readonly max: number;
}

export type GroupKey = 'shape' | 'attention' | 'feed_forward' | 'vocabulary' | 'tokenizer' | 'training';

export interface FieldSpec {
  readonly key: NumberKey;
  readonly group: GroupKey;
  readonly families: readonly Family[];
  readonly termKey?: string;
  readonly moeWording?: true;
}

export interface GroupSpec {
  readonly key: GroupKey;
  readonly termKey: string | null;
  readonly moeTermKey?: string;
  readonly intro: boolean;
  readonly moeWording?: true;
}

export interface ViewGroup extends GroupSpec {
  readonly fields: readonly FieldSpec[];
}

export type ShareTone =
  | 'primary'
  | 'secondary'
  | 'tertiary'
  | 'primary-container'
  | 'secondary-container'
  | 'tertiary-container';

export interface PartSpec {
  readonly key: PartKey;
  readonly tone: ShareTone;
  readonly moeTerm?: string;
}

export interface PartRow {
  readonly key: PartKey;
  readonly termKey: string;
  readonly tone: ShareTone;
  readonly value: number;
  readonly ratio: number;
}

export interface MemoryOption {
  readonly key: 'adamw' | 'adamw8';
  readonly optimizer: number;
  readonly activations: number;
  readonly runtime: number;
  readonly total: number;
  readonly fit: Fit;
}

export const FAMILIES: readonly Family[] = ['dense_decoder', 'moe_decoder', 'encoder_decoder'];

const DECODERS: readonly Family[] = ['dense_decoder', 'moe_decoder'];

const EVERY_FAMILY: readonly Family[] = FAMILIES;

export const LIMITS: Readonly<Record<NumberKey, Limit>> = {
  layers: { min: 1, max: 256 },
  encoder_layers: { min: 1, max: 128 },
  decoder_layers: { min: 1, max: 128 },
  hidden_size: { min: 16, max: 65_536 },
  heads: { min: 1, max: 1_024 },
  kv_heads: { min: 1, max: 1_024 },
  intermediate_size: { min: 16, max: 1_048_576 },
  experts: { min: 2, max: 512 },
  experts_per_token: { min: 1, max: 512 },
  vocab_size: { min: 256, max: 1_048_576 },
  context_length: { min: 64, max: 1_048_576 },
  seq_len: { min: 64, max: 131_072 },
  batch: { min: 1, max: 1_024 },
};

export const GROUPS: readonly GroupSpec[] = [
  { key: 'shape', termKey: null, intro: false },
  { key: 'attention', termKey: 'attention', intro: true },
  { key: 'feed_forward', termKey: 'feed_forward', moeTermKey: 'experts', intro: true, moeWording: true },
  { key: 'vocabulary', termKey: null, intro: false },
  { key: 'tokenizer', termKey: 'tokenizer', intro: true },
  { key: 'training', termKey: null, intro: true },
];

export const FIELDS: readonly FieldSpec[] = [
  { key: 'layers', group: 'shape', families: DECODERS },
  { key: 'encoder_layers', group: 'shape', families: ['encoder_decoder'] },
  { key: 'decoder_layers', group: 'shape', families: ['encoder_decoder'] },
  { key: 'hidden_size', group: 'shape', families: EVERY_FAMILY },
  { key: 'heads', group: 'attention', families: EVERY_FAMILY },
  { key: 'kv_heads', group: 'attention', families: DECODERS, termKey: 'kv_heads' },
  { key: 'intermediate_size', group: 'feed_forward', families: EVERY_FAMILY, moeWording: true },
  { key: 'experts', group: 'feed_forward', families: ['moe_decoder'] },
  { key: 'experts_per_token', group: 'feed_forward', families: ['moe_decoder'] },
  { key: 'vocab_size', group: 'vocabulary', families: EVERY_FAMILY },
  { key: 'context_length', group: 'vocabulary', families: EVERY_FAMILY },
  { key: 'seq_len', group: 'training', families: EVERY_FAMILY },
  { key: 'batch', group: 'training', families: EVERY_FAMILY },
];

export const PARTS: readonly PartSpec[] = [
  { key: 'embeddings', tone: 'tertiary' },
  { key: 'attention', tone: 'primary' },
  { key: 'feed_forward', tone: 'secondary', moeTerm: 'experts' },
  { key: 'router', tone: 'tertiary-container' },
  { key: 'norms', tone: 'secondary-container' },
  { key: 'lm_head', tone: 'primary-container' },
];

export const FIT_ICONS: Readonly<Record<FitVerdict, string>> = {
  fits: 'fa-circle-check',
  tight: 'fa-triangle-exclamation',
  too_large: 'fa-circle-xmark',
  cpu_only: 'fa-microchip',
  unknown: 'fa-circle-question',
};

export const FAMILY_TERMS: Readonly<Record<Family, string>> = {
  dense_decoder: 'token',
  moe_decoder: 'moe',
  encoder_decoder: 'encoder_decoder',
};

export const DEFAULT_SEQ_LEN = 1_024;

export const DEFAULT_BATCH = 8;

export const DEFAULT_BLUEPRINT: Blueprint = {
  family: 'dense_decoder',
  layers: 12,
  encoder_layers: 6,
  decoder_layers: 6,
  hidden_size: 768,
  heads: 12,
  kv_heads: 4,
  intermediate_size: 2_048,
  experts: 8,
  experts_per_token: 2,
  vocab_size: 32_000,
  context_length: 2_048,
  seq_len: DEFAULT_SEQ_LEN,
  batch: DEFAULT_BATCH,
  tie_embeddings: true,
  tokenizer: '',
};

export const NAME_MAX = 120;

export const NOTES_MAX = 4000;

export const TOKENIZER_MAX = 200;

export const DRAFTS_PAGE_SIZE = 24;

export const SOURCES_PAGE_SIZE = 200;

export const DATASET_READY = 'ready';

export const TOKENIZER_EXAMPLE = 'Qwen/Qwen3-0.6B';
