export interface Gpu {
  readonly index: number;
  readonly name: string;
  readonly memory_bytes: number;
  readonly compute_capability: string | null;
}

export interface Machine {
  readonly gpus: readonly Gpu[];
  readonly driver: string | null;
  readonly ram_bytes: number;
  readonly cpu_count: number;
  readonly system: string;
  readonly python: string;
}

export interface Storage {
  readonly path: string;
  readonly free_bytes: number;
  readonly total_bytes: number;
}

export type PartPurpose = 'training' | 'quantization' | 'speed' | 'gguf';

export interface Part {
  readonly name: string;
  readonly purpose: PartPurpose;
  readonly version: string | null;
  readonly cuda: boolean | null;
}

export interface HuggingFaceStatus {
  readonly configured: boolean;
  readonly hint: string;
  readonly account: string;
}

export type GpuChoice = 'automatic' | 'chosen';

export interface SystemOverview {
  readonly machine: Machine;
  readonly selected_gpus: readonly number[];
  readonly gpu_choice: GpuChoice;
  readonly usable_vram_bytes: number;
  readonly storage: Storage;
  readonly parts: readonly Part[];
  readonly huggingface: HuggingFaceStatus;
}

export interface GpuSelection {
  readonly gpus: readonly number[];
}

export interface HuggingFaceToken {
  readonly token: string;
}

export const TRAINING_PARTS: readonly string[] = ['torch', 'transformers', 'peft', 'trl'];
