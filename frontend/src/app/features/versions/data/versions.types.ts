export type VersionKind = 'base' | 'scratch_root' | 'lora';

export interface DeltaSummary {
  readonly total_norm: number | null;
  readonly change_from_parent: number | null;
  readonly parameters: number | null;
}

export interface Version {
  readonly id: string;
  readonly number: number;
  readonly name: string;
  readonly notes: string;
  readonly kind: VersionKind;
  readonly parent_id: string | null;
  readonly is_active: boolean;
  readonly children_count: number | null;
  readonly size_bytes: number;
  readonly full_size_bytes: number;
  readonly lora_rank: number | null;
  readonly trains_biases: boolean;
  readonly delta: DeltaSummary | null;
  readonly metrics: Readonly<Record<string, unknown>>;
  readonly created_at: string;
  readonly created_by: string | null;
}

export interface VersionChange {
  readonly name?: string;
  readonly notes?: string;
}

export interface VersionNode {
  readonly version: Version;
  readonly children: readonly VersionNode[];
}

export interface SizeShare {
  readonly ratio: number;
  readonly key: string;
  readonly percent: string;
}

export type ExportFormat = 'lora' | 'merged' | 'gguf';

export type ExportQuality = 'f16' | 'bf16' | 'q8_0';

export type ExportStatus = 'queued' | 'running' | 'ready' | 'failed';

export interface VersionExport {
  readonly id: string;
  readonly version: string;
  readonly format: ExportFormat;
  readonly out_type: ExportQuality | '';
  readonly status: ExportStatus;
  readonly error_code: string;
  readonly path: string;
  readonly size_bytes: number;
  readonly downloadable: boolean;
  readonly created_at: string;
  readonly finished_at: string | null;
  readonly created_by: string | null;
}

export interface NewExport {
  readonly format: ExportFormat;
  readonly out_type?: ExportQuality;
}

export interface LayerChange {
  readonly layer: number;
  readonly norms: Readonly<Record<string, number>>;
}

export interface VersionChanges {
  readonly version: string;
  readonly modules: readonly string[];
  readonly layers: readonly LayerChange[];
  readonly total_norm: number | null;
  readonly change_from_parent: number | null;
  readonly parameters: number | null;
  readonly rank: number | null;
}

export type ModuleKind = 'attention' | 'feed_forward' | 'other';

export interface ChangeCell {
  readonly module: string;
  readonly norm: number | null;
  readonly tint: number;
}

export interface ChangeRow {
  readonly layer: number;
  readonly cells: readonly ChangeCell[];
}

export interface ChangeGroup {
  readonly kind: ModuleKind;
  readonly modules: readonly string[];
  readonly mean: number;
}

export interface ChangeMap {
  readonly groups: readonly ChangeGroup[];
  readonly modules: readonly string[];
  readonly rows: readonly ChangeRow[];
  readonly topLayers: readonly number[];
  readonly leading: ModuleKind | 'even' | null;
}

export interface RenameDialogData {
  readonly version: Version;
}

export interface VersionDialogData {
  readonly version: Version;
}

export interface ExportChoice {
  readonly format: ExportFormat;
  readonly blocker: string | null;
}

export const PAGE_SIZE = 200;

export const NAME_MAX = 120;

export const NOTES_MAX = 4000;

export const SLIVER = 0.001;

export const MAX_INDENT_DEPTH = 4;

export const EXPORT_FORMATS: readonly ExportFormat[] = ['lora', 'merged', 'gguf'];

export const EXPORT_QUALITIES: readonly ExportQuality[] = ['f16', 'bf16', 'q8_0'];

export const UNFINISHED_EXPORTS: readonly ExportStatus[] = ['queued', 'running'];

export const EXPORT_FAILURES: readonly string[] = [
  'training_parts_missing',
  'converter_unavailable',
  'conversion_failed',
  'out_of_memory',
  'exporter_crashed',
  'nothing_to_merge',
  'failed',
];

export const EXPORT_STATUS_ICONS: Readonly<Record<ExportStatus, string>> = {
  queued: 'fa-clock',
  running: 'fa-hourglass-half',
  ready: 'fa-circle-check',
  failed: 'fa-circle-exclamation',
};

export const TOP_LAYERS = 3;

export const MAX_TINT = 48;

export const EVEN_SHARE = 0.1;
