import type { ApiError } from '@core/http/api.types';
import type { StatusTone } from '@shared/status/status.types';

export type RunStatus = 'queued' | 'preparing' | 'training' | 'saving' | 'completed' | 'failed' | 'cancelled';

export type RunStage = '' | 'data' | 'tokenizer' | 'model' | 'parent' | 'training' | 'oom_retry';

export type RunKind = 'lora' | 'pretrain';

export type Optimizer = 'adamw_torch' | 'adamw_8bit';

export type FitVerdict = 'fits' | 'tight' | 'too_large' | 'cpu_only' | 'unknown';

export type LoraRank = 4 | 8 | 16 | 32 | 64 | 128 | 256;

export interface VersionRef {
  readonly id: string;
  readonly name: string;
  readonly number: number;
}

export interface Hyperparams {
  readonly epochs: number;
  readonly max_steps: number | null;
  readonly learning_rate: number;
  readonly lora_rank: LoraRank;
  readonly lora_alpha: number;
  readonly lora_dropout: number;
  readonly use_rslora: boolean;
  readonly train_biases: boolean;
  readonly max_seq_len: number;
  readonly batch_size: number;
  readonly grad_accum: number;
  readonly quantize_4bit: boolean;
  readonly gradient_checkpointing: boolean;
}

export interface PretrainSettings {
  readonly optim?: Optimizer;
}

export type RunHyperparams = Readonly<Partial<Hyperparams>> & {
  readonly warmup_ratio?: number;
  readonly pretrain?: PretrainSettings;
};

export type DatasetStatus = 'queued' | 'importing' | 'ready' | 'failed' | 'cancelled';

export interface RunDataset {
  readonly id: string;
  readonly name: string;
  readonly rows: number;
  readonly max_rows: number | null;
}

export interface DatasetWire {
  readonly id: string;
  readonly name: string;
  readonly status: DatasetStatus;
  readonly rows: number;
  readonly format: string;
  readonly source: string;
  readonly repo_id: string;
  readonly has_thinking: boolean;
}

export interface LibraryDataset {
  readonly id: string;
  readonly name: string;
  readonly rows: number;
  readonly hasThinking: boolean;
}

export interface DatasetChoice {
  readonly id: string;
  readonly maxRows: number | null;
}

export interface Run {
  readonly id: string;
  readonly project: string;
  readonly kind: RunKind;
  readonly draft: string | null;
  readonly corrections_from: readonly string[];
  readonly name: string;
  readonly notes: string;
  readonly starts_from: VersionRef | null;
  readonly version: VersionRef | null;
  readonly use_corrections: boolean;
  readonly datasets: readonly RunDataset[];
  readonly hyperparams: RunHyperparams;
  readonly activate_when_done: boolean;
  readonly status: RunStatus;
  readonly stage: RunStage;
  readonly examples: number | null;
  readonly skipped: number | null;
  readonly tokens: number | null;
  readonly step: number;
  readonly total_steps: number;
  readonly epoch: number | null;
  readonly loss: number | null;
  readonly max_seq_len: number | null;
  readonly gpu_indices: readonly number[];
  readonly error_code: string;
  readonly error_detail: string;
  readonly cancel_requested: boolean;
  readonly started_at: string | null;
  readonly finished_at: string | null;
  readonly created_at: string;
  readonly created_by: string | null;
}

export interface NewRun {
  readonly project: string;
  readonly starts_from: string | null;
  readonly name: string;
  readonly use_corrections: boolean;
  readonly datasets: readonly { readonly id: string; readonly max_rows: number | null }[];
  readonly activate_when_done: boolean;
  readonly hyperparams: Readonly<Partial<Hyperparams>>;
}

export interface Fit {
  readonly verdict: FitVerdict;
  readonly required_bytes: number | null;
  readonly available_bytes: number;
}

export interface Plan {
  readonly hyperparams: Readonly<Partial<Hyperparams>>;
  readonly corrections: number;
  readonly fit: Fit;
  readonly gpu_indices: readonly number[];
}

export interface Metric {
  readonly step: number;
  readonly epoch: number | null;
  readonly loss: number | null;
  readonly learning_rate: number | null;
  readonly grad_norm: number | null;
}

export interface Turn {
  readonly role: string;
  readonly content: string;
  readonly thinking?: string;
}

export interface ConversationRef {
  readonly id: string;
  readonly title: string;
}

export interface Example {
  readonly id: string;
  readonly conversation: ConversationRef;
  readonly messages: readonly Turn[];
  readonly corrected: boolean;
  readonly thinking_corrected: boolean;
  readonly approved_by: string | null;
  readonly updated_at: string;
}

export interface VersionWire {
  readonly id: string;
  readonly number: number;
  readonly name: string;
  readonly kind: 'base' | 'scratch_root' | 'lora';
  readonly is_active: boolean;
  readonly size_bytes: number;
  readonly full_size_bytes: number;
}

export interface ProjectNameWire {
  readonly id: string;
  readonly name: string;
}

export type SourceNames = Readonly<Record<string, string>>;

export interface RunSource {
  readonly id: string;
  readonly name: string | null;
}

export interface StartVersion {
  readonly id: string;
  readonly number: number;
  readonly name: string;
  readonly isActive: boolean;
}

export interface VersionSize {
  readonly sizeBytes: number;
  readonly fullSizeBytes: number;
}

export type StartResult = { readonly run: Run } | { readonly error: ApiError };

export type LossTrend = 'too_early' | 'falling' | 'levelled_off' | 'rising';

export interface LossReading {
  readonly trend: LossTrend;
  readonly first: number | null;
  readonly latest: number | null;
}

export interface StepSample {
  readonly at: number;
  readonly step: number;
}

export interface Draft {
  readonly startsFrom: string | null;
  readonly name: string;
  readonly useCorrections: boolean;
  readonly datasets: readonly DatasetChoice[];
  readonly activateWhenDone: boolean;
  readonly settings: Readonly<Hyperparams>;
}

export type SettingKey = keyof Hyperparams;

export interface NumberField {
  readonly key: SettingKey;
  readonly labelKey: string;
  readonly hintKey: string;
  readonly min: number;
  readonly max: number;
  readonly step: number | 'any';
  readonly integer: boolean;
  readonly optional: boolean;
  readonly termKey: string | null;
}

export interface SwitchField {
  readonly key: SettingKey;
  readonly labelKey: string;
  readonly hintKey: string;
  readonly termKey: string | null;
}

export interface Preset<T extends number> {
  readonly value: T;
  readonly labelKey: string;
}

export type ProblemKind = 'required' | 'whole' | 'range';

export interface FieldProblem {
  readonly key: SettingKey;
  readonly kind: ProblemKind;
}

export interface ChartSeries {
  readonly id: string;
  readonly label: string;
  readonly values: readonly (number | null)[];
  readonly color: 'primary' | 'tertiary';
  readonly axis: 'left' | 'right';
  readonly axisTitle: string;
}

export interface ChartData {
  readonly steps: readonly number[];
  readonly series: readonly ChartSeries[];
  readonly stepTitle: string;
  readonly summary: string;
}

export type TrainingView = 'runs' | 'examples';

export interface ChartSnapshot {
  readonly data: ChartData;
  readonly rtl: boolean;
  readonly locale: string;
  readonly scheme: number;
}

export interface ChartPalette {
  readonly primary: string;
  readonly tertiary: string;
  readonly grid: string;
  readonly text: string;
}

export type RunSettingKey = SettingKey | 'warmup_ratio' | 'optim';

export interface SettingRow {
  readonly key: RunSettingKey;
  readonly labelKey: string;
  readonly text: string;
  readonly termKey: string | null;
}

export interface SizeShare {
  readonly key: string;
  readonly percent: string;
  readonly ratio: number;
  readonly bytes: number;
}

export interface StatusLook {
  readonly icon: string;
  readonly tone: StatusTone;
}

export const RUN_PAGE_SIZES: readonly number[] = [5, 10, 25];

export const EXAMPLE_PAGE_SIZES: readonly number[] = [5, 10, 25];

export const DEFAULT_PAGE_SIZE = 10;

export const VERSIONS_PAGE_SIZE = 200;

export const DATASETS_PAGE_SIZE = 200;

export const METRICS_PAGE_SIZE = 200;

export const RUNS_POLL_MS = 3000;

export const RUN_POLL_MS = 2000;

export const CLOCK_MS = 1000;

export const NAME_MAX = 120;

export const FINISHED_STATUSES: readonly RunStatus[] = ['completed', 'failed', 'cancelled'];

export const STOPPABLE_STATUSES: readonly RunStatus[] = ['queued', 'preparing', 'training', 'saving'];

export const STATUS_LOOKS: Readonly<Record<RunStatus, StatusLook>> = {
  queued: { icon: 'fa-hourglass-half', tone: 'neutral' },
  preparing: { icon: 'fa-gears', tone: 'ok' },
  training: { icon: 'fa-graduation-cap', tone: 'ok' },
  saving: { icon: 'fa-floppy-disk', tone: 'ok' },
  completed: { icon: 'fa-circle-check', tone: 'ok' },
  failed: { icon: 'fa-circle-exclamation', tone: 'error' },
  cancelled: { icon: 'fa-ban', tone: 'neutral' },
};

export const KIND_WORDED_STAGES: readonly string[] = ['tokenizer', 'model'];

export const PRETRAIN_FAILURE_CODES: readonly string[] = [
  'no_examples',
  'out_of_memory',
  'load_failed',
  'trainer_crashed',
  'interrupted',
  'bad_settings',
];

export const FAILURE_CODES: readonly string[] = [
  'no_examples',
  'out_of_memory',
  'load_failed',
  'training_parts_missing',
  'trainer_crashed',
  'interrupted',
  'bad_settings',
  'failed',
];

export const EPOCH_RANGE = { min: 1, max: 5, step: 1 } as const;

export const RANK_PRESETS: readonly Preset<LoraRank>[] = [
  { value: 8, labelKey: 'training.form.rank.small' },
  { value: 16, labelKey: 'training.form.rank.medium' },
  { value: 64, labelKey: 'training.form.rank.large' },
];

export const RANK_CHOICES: readonly LoraRank[] = [4, 8, 16, 32, 64, 128, 256];

export const RATE_PRESETS: readonly Preset<number>[] = [
  { value: 1e-4, labelKey: 'training.form.rate.gentle' },
  { value: 2e-4, labelKey: 'training.form.rate.normal' },
  { value: 5e-4, labelKey: 'training.form.rate.strong' },
];

export const EXACT_FIELDS: readonly NumberField[] = [
  {
    key: 'epochs',
    labelKey: 'training.form.epochs.label',
    hintKey: 'training.expert.epochsHint',
    min: 0.1,
    max: 100,
    step: 'any',
    integer: false,
    optional: false,
    termKey: 'epoch',
  },
  {
    key: 'learning_rate',
    labelKey: 'training.form.rate.label',
    hintKey: 'training.expert.rateHint',
    min: 1e-7,
    max: 1e-2,
    step: 'any',
    integer: false,
    optional: false,
    termKey: 'learning_rate',
  },
];

export const EXPERT_FIELDS: readonly NumberField[] = [
  {
    key: 'max_steps',
    labelKey: 'training.expert.maxSteps',
    hintKey: 'training.expert.maxStepsHint',
    min: 1,
    max: 1_000_000,
    step: 1,
    integer: true,
    optional: true,
    termKey: null,
  },
  {
    key: 'max_seq_len',
    labelKey: 'training.expert.maxSeqLen',
    hintKey: 'training.expert.maxSeqLenHint',
    min: 128,
    max: 131072,
    step: 1,
    integer: true,
    optional: false,
    termKey: 'token',
  },
  {
    key: 'batch_size',
    labelKey: 'training.expert.batchSize',
    hintKey: 'training.expert.batchSizeHint',
    min: 1,
    max: 64,
    step: 1,
    integer: true,
    optional: false,
    termKey: null,
  },
  {
    key: 'grad_accum',
    labelKey: 'training.expert.gradAccum',
    hintKey: 'training.expert.gradAccumHint',
    min: 1,
    max: 256,
    step: 1,
    integer: true,
    optional: false,
    termKey: null,
  },
  {
    key: 'lora_alpha',
    labelKey: 'training.expert.loraAlpha',
    hintKey: 'training.expert.loraAlphaHint',
    min: 1,
    max: 1024,
    step: 1,
    integer: true,
    optional: false,
    termKey: null,
  },
  {
    key: 'lora_dropout',
    labelKey: 'training.expert.loraDropout',
    hintKey: 'training.expert.loraDropoutHint',
    min: 0,
    max: 0.5,
    step: 'any',
    integer: false,
    optional: false,
    termKey: null,
  },
];

export const EXPERT_SWITCHES: readonly SwitchField[] = [
  {
    key: 'use_rslora',
    labelKey: 'training.expert.rslora',
    hintKey: 'training.expert.rsloraHint',
    termKey: null,
  },
  {
    key: 'train_biases',
    labelKey: 'training.expert.biases',
    hintKey: 'training.expert.biasesHint',
    termKey: null,
  },
  {
    key: 'quantize_4bit',
    labelKey: 'training.expert.quantize',
    hintKey: 'training.expert.quantizeHint',
    termKey: 'quantization',
  },
  {
    key: 'gradient_checkpointing',
    labelKey: 'training.expert.checkpointing',
    hintKey: 'training.expert.checkpointingHint',
    termKey: null,
  },
];

export const FALLBACK_SETTINGS: Readonly<Hyperparams> = {
  epochs: 2,
  max_steps: null,
  learning_rate: 2e-4,
  lora_rank: 16,
  lora_alpha: 32,
  lora_dropout: 0,
  use_rslora: false,
  train_biases: false,
  max_seq_len: 2048,
  batch_size: 1,
  grad_accum: 8,
  quantize_4bit: false,
  gradient_checkpointing: true,
};

export const EXPERT_ONLY_KEYS: readonly SettingKey[] = [
  'max_steps',
  'max_seq_len',
  'batch_size',
  'grad_accum',
  'lora_alpha',
  'lora_dropout',
  'use_rslora',
  'train_biases',
  'quantize_4bit',
  'gradient_checkpointing',
];

export const SETTING_LABELS: Readonly<Record<RunSettingKey, string>> = {
  epochs: 'training.form.epochs.label',
  max_steps: 'training.expert.maxSteps',
  learning_rate: 'training.form.rate.label',
  optim: 'training.settingsUsed.optimizer',
  lora_rank: 'training.expert.rank',
  lora_alpha: 'training.expert.loraAlpha',
  lora_dropout: 'training.expert.loraDropout',
  use_rslora: 'training.expert.rslora',
  train_biases: 'training.expert.biases',
  max_seq_len: 'training.expert.maxSeqLen',
  batch_size: 'training.expert.batchSize',
  grad_accum: 'training.expert.gradAccum',
  warmup_ratio: 'training.settingsUsed.warmup',
  quantize_4bit: 'training.expert.quantize',
  gradient_checkpointing: 'training.expert.checkpointing',
};

export const SIMPLE_SETTING_KEYS: readonly RunSettingKey[] = ['epochs', 'lora_rank', 'learning_rate', 'optim'];

export const SLIVER = 0.001;

export const TREND_ICONS: Readonly<Record<LossTrend, string>> = {
  too_early: 'fa-hourglass-half',
  falling: 'fa-arrow-trend-down',
  levelled_off: 'fa-minus',
  rising: 'fa-arrow-trend-up',
};

export const LOSS_MIN_POINTS = 8;

export const LOSS_FALL = 0.03;

export const LOSS_RISE = 0.05;

export const PACE_SAMPLES = 8;
