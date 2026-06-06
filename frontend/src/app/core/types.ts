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

export interface CuratedModel {
  repo_id: string;
  label: string;
  params: string;
  context: string;
  arabic: string;
  license: string;
  note: string;
  recommended: boolean;
  fast_4bit_repo?: string;
  default_seq_len?: number;
  default_lora_r?: number;
}

export interface SystemInfo {
  gpu_vram_gb: number;
  default_base_model: string;
  max_train_seq_len: number;
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
