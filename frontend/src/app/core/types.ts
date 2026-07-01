/** TypeScript mirrors of the backend schemas (backend/app/core/models.py).
 *  Technical field names stay in English to match the API exactly. */

export type RunStatus =
  | 'pending' | 'preparing' | 'running' | 'completed' | 'failed' | 'cancelled';
export type TaskStatus = 'todo' | 'in_progress' | 'done';
export type MessageRole = 'system' | 'user' | 'assistant';

export interface Project {
  id: string;
  name: string;
  description: string;
  kind: string;                 // "finetune" | "scratch"
  base_model_repo: string;
  base_model_local_path: string | null;
  active_version_id: string | null;
  default_train_config: Record<string, unknown>;
  language: string;
  created_at: string;
  updated_at: string;
  session_count: number;
  task_count: number;
  version_count: number;
}

/** A from-scratch decoder architecture (mirrors features/architect/schemas). */
export interface ArchitectureSpec {
  family: 'llama' | 'qwen3' | 'mistral' | 'qwen3_moe' | 'mixtral';
  num_hidden_layers: number;
  hidden_size: number;
  num_attention_heads: number;
  num_key_value_heads?: number | null;
  intermediate_size?: number | null;
  vocab_size: number;
  max_position_embeddings: number;
  tie_word_embeddings: boolean;
  num_experts: number;
  num_experts_per_tok: number;
  moe_intermediate_size?: number | null;
}

export interface FeasibilityEstimate {
  spec: ArchitectureSpec;
  params: {
    embeddings: number; attention: number; mlp: number; other: number;
    total_params: number; active_params: number;
    total_params_human: string; active_params_human: string;
  };
  memory: {
    weights_gb: number; gradients_gb: number; optimizer_gb: number;
    activation_gb: number; total_gb: number; gpu_vram_gb: number;
    host_ram_gb: number;
    verdict: 'fits_vram' | 'cpu_offload' | 'nvme_offload' | 'exceeds_disk';
    paging_required: boolean; will_finish: boolean;
  };
  warnings: string[];
  suggested_gpu_budget_gb: number;
}

export interface DatasetHit {
  repo_id: string;
  downloads?: number | null;
  likes?: number | null;
  tags?: string[];
  note?: string;
}

/** Architecture facts read from a model's config.json (e.g. an embedding source). */
export interface ModelArchitecture {
  repo_id: string;
  model_type: string | null;
  architectures: string[];
  num_hidden_layers: number | null;
  hidden_size: number | null;
  num_attention_heads: number | null;
  num_key_value_heads: number | null;
  vocab_size: number | null;
  max_position_embeddings: number | null;
  is_moe: boolean;
  num_experts: number | null;
  num_experts_per_tok: number | null;
}

export interface Task {
  id: string;
  project_id: string;
  title: string;
  description: string;
  objective: string;
  status: TaskStatus;
  order_index: number;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: MessageRole;
  content: string;
  original_content: string | null;
  corrected: boolean;
  approved: boolean;
  include_in_training: boolean;
  order_index: number;
  created_at: string;
  meta: Record<string, unknown>;
}

export interface ChatSession {
  id: string;
  project_id: string;
  task_id: string | null;
  title: string;
  system_prompt: string;
  correction_prompt: string;   // editable prompt for the self-correct "magic wand"
  model_version_id: string | null;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
  approved_count: number;
  model_label?: string | null;   // which model this chat talks to
  is_base_model?: boolean;       // true = raw base model, false = fine-tuned (has adapter)
}

export interface ModelVersion {
  id: string;
  project_id: string;
  parent_id: string | null;
  training_run_id: string | null;
  label: string;
  notes: string;
  is_base: boolean;
  is_active: boolean;
  adapter_path: string | null;
  merged_path: string | null;
  metrics: Record<string, unknown>;
  depth: number;
  created_at: string;
}

export interface VersionNode extends ModelVersion {
  children: VersionNode[];
}

export interface TrainingRun {
  id: string;
  project_id: string;
  name: string;
  parent_version_id: string | null;
  result_version_id: string | null;
  status: RunStatus;
  config: Record<string, any>;
  dataset_path: string | null;
  num_examples: number;
  progress: { total_steps?: number; step?: number; [k: string]: unknown };
  metrics: Record<string, unknown>;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

/** An automated self-improvement loop (التحسين التلقائي). Reuses RunStatus. */
export interface AutoEnhanceLoop {
  id: string;
  project_id: string;
  name: string;
  status: RunStatus;
  config: {
    generations: number;
    turns_per_generation: number;
    thresholds: { logic: number; language: number; context: number; factuality: number };
    max_correction_rounds: number;
    topic_source: 'tasks' | 'free';
    hyperparams: Record<string, unknown>;
    parent_version_id: string | null;
    ask_prompt?: string;
    eval_prompt?: string;
  };
  progress: {
    generation?: number; turn?: number; phase?: string;
    last_scores?: Record<string, number>; current_run_id?: string; [k: string]: unknown;
  };
  results: { generations?: Array<Record<string, unknown>>; [k: string]: unknown };
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

/** One live event streamed over the auto-enhance WebSocket (`{type:'event',data}`). */
export interface AutoEnhanceEvent {
  type:
    | 'generation_start' | 'turn_start' | 'ask' | 'answer' | 'evaluation'
    | 'correction' | 'turn_done' | 'training_start' | 'training_status'
    | 'training_skipped' | 'generation_done' | 'loop_done' | 'error';
  ts: number;
  generation?: number;
  turn?: number;
  round?: number;
  text?: string;
  message_id?: string;
  scores?: Record<string, number>;
  approved?: boolean;
  rounds?: number;
  run_id?: string;
  num_examples?: number;
  status?: string;
  progress?: Record<string, unknown>;
  avg_scores?: Record<string, number>;
  version_id?: string | null;
  versions?: Array<string | null>;
  reason?: string;
  message?: string;
}

/** A model listed live from the HuggingFace API (or the local registry offline). */
export interface HubModel {
  repo_id: string;
  label: string;
  downloads?: number | null;
  likes?: number | null;
  tags?: string[];
  license?: string | null;
  params?: string | null;
  pipeline_tag?: string | null;
  gated?: boolean;
  source?: 'hub' | 'local';
  note?: string;
}

/** One background download's status (models/downloads). */
export interface DownloadState {
  repo_id: string;
  repo_type: 'model' | 'dataset';
  status: 'pending' | 'downloading' | 'done' | 'error' | 'absent';
  local_path?: string | null;
  error?: string | null;
  bytes_done: number;
  total_bytes: number;
  percent: number;
}

/** A detected CUDA GPU (mirrors core/hardware.detect_gpus). */
export interface GpuInfo {
  index: number;
  name: string;
  total_vram_gb: number;
  compute_capability: string | null;
}

export interface SystemInfo {
  gpus: GpuInfo[];
  selected_gpu: GpuInfo | null;
  selected_gpus: GpuInfo[];
  gpu_vram_gb: number;
  system_ram_gb: number;
  cuda_available: boolean;
  default_base_model: string;
  max_train_seq_len: number;
  onboarded: boolean;
  engine: {
    runtime_available: boolean;
    loaded: boolean;
    cuda?: boolean;
    device?: string;
    vram_total_gb?: number;
    vram_free_gb?: number;
    vram_used_gb?: number;
  };
}

/** Persisted user settings (mirrors features/settings.public()). */
export interface AppSettings {
  onboarded: boolean;
  selected_gpu_index: number | null;          // legacy single choice
  selected_gpu_indices: number[] | null;      // null ⇒ auto (largest GPU)
  gpu_vram_gb_override: number | null;
  theme: 'light' | 'dark';
  tokens: Record<string, { configured: boolean; hint: string }>;
}

/** Snapshot from GET /api/debug/status. */
export interface DebugStatus {
  hardware: SystemInfo & Record<string, unknown>;
  gpu_live: Array<{
    index: number; name: string; util_pct: number | null;
    mem_used_gb: number | null; mem_total_gb: number | null; temp_c: number | null;
  }>;
  engine: Record<string, any>;
  downloads: DownloadState[];
  active_runs: Array<{
    id: string; name: string; project_id: string; status: string;
    pid: number | null; started_at: string | null;
  }>;
  settings: { selected_gpu_indices: number[] | null; onboarded: boolean };
  env: { python: string; torch: string | null; transformers: string | null; ml_available: boolean };
}

/** One live point streamed over the training WebSocket. */
export interface MetricPoint {
  event?: string;
  step?: number;
  total_steps?: number;
  epoch?: number;
  loss?: number;
  learning_rate?: number;
  grad_norm?: number;
  vram_reserved_gb?: number;
  num_examples?: number;
  backend?: string;
  ts?: number;
}
