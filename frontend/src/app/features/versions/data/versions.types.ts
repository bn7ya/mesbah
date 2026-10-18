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

export interface RenameDialogData {
  readonly version: Version;
}

export const PAGE_SIZE = 200;

export const NAME_MAX = 120;

export const NOTES_MAX = 4000;

export const SLIVER = 0.001;
