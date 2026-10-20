import type { ApiError } from '@core/http/api.types';

export type EngineKind = 'builtin' | 'vllm' | 'llamacpp' | 'ollama' | 'openai';

export type ConnectableKind = Exclude<EngineKind, 'builtin'>;

export type DeviceKind = 'none' | 'cpu' | 'gpu' | 'other';

export interface LoadedBase {
  readonly id: string;
  readonly repo_id: string;
}

export interface LoadedProject {
  readonly id: string;
  readonly name: string;
}

export interface LoadedVersion {
  readonly id: string;
  readonly name: string;
  readonly number: number;
  readonly project: LoadedProject;
}

export interface EngineState {
  readonly running: boolean;
  readonly loaded: boolean;
  readonly busy: boolean;
  readonly device: string | null;
  readonly quantized: boolean;
  readonly base_model: LoadedBase | null;
  readonly versions: readonly LoadedVersion[];
}

export interface Engine {
  readonly id: string;
  readonly name: string;
  readonly kind: EngineKind;
  readonly base_url: string;
  readonly model_name: string;
  readonly has_api_key: boolean;
  readonly enabled: boolean;
  readonly is_default: boolean;
  readonly last_seen_at: string | null;
  readonly state: EngineState;
}

export interface NewEngine {
  readonly name: string;
  readonly kind: ConnectableKind;
  readonly base_url: string;
  readonly model_name?: string;
  readonly api_key?: string;
  readonly is_default?: boolean;
}

export interface EngineChange {
  readonly name?: string;
  readonly base_url?: string;
  readonly model_name?: string;
  readonly api_key?: string;
  readonly enabled?: boolean;
  readonly is_default?: boolean;
}

export interface ApiKey {
  readonly id: string;
  readonly name: string;
  readonly prefix: string;
  readonly owner: string | null;
  readonly last_used_at: string | null;
  readonly created_at: string;
}

export interface CreatedApiKey extends ApiKey {
  readonly key: string;
}

export type KeyResult = { readonly key: CreatedApiKey } | { readonly error: ApiError };

export interface ProjectSlugWire {
  readonly slug: string;
}

export interface Device {
  readonly kind: DeviceKind;
  readonly index: number | null;
  readonly raw: string;
}

export interface Snippet {
  readonly id: string;
  readonly labelKey: string;
  readonly code: string;
}

export interface GuideApi {
  readonly id: 'openai' | 'ollama';
  readonly address: string;
  readonly snippets: readonly Snippet[];
}

export interface StartCommand {
  readonly id: string;
  readonly command: string;
  readonly labelKey: string;
  readonly bodyKey: string;
}

export interface EngineFormData {
  readonly engine: Engine | null;
}

export const CONNECTABLE_KINDS: readonly ConnectableKind[] = ['vllm', 'ollama', 'llamacpp', 'openai'];

export const KINDS_WITH_MODEL_NAME: readonly EngineKind[] = ['llamacpp', 'openai'];

export const KIND_TERMS: Readonly<Partial<Record<EngineKind, string>>> = { vllm: 'vllm', ollama: 'ollama' };

export const START_COMMANDS: readonly StartCommand[] = [
  {
    id: 'pip',
    command: 'pip install "mesbah[train]"',
    labelKey: 'serving.builtin.stopped.pip',
    bodyKey: 'serving.builtin.stopped.pipBody',
  },
  {
    id: 'docker',
    command: 'docker compose --profile ml up',
    labelKey: 'serving.builtin.stopped.docker',
    bodyKey: 'serving.builtin.stopped.dockerBody',
  },
  {
    id: 'docker-gpu',
    command: 'docker compose -f compose.yaml -f compose.gpu.yaml up',
    labelKey: 'serving.builtin.stopped.dockerGpu',
    bodyKey: 'serving.builtin.stopped.dockerGpuBody',
  },
];

export const EXAMPLE_ADDRESS = 'http://gpu-box:8000';

export const ENGINES_PAGE_SIZE = 200;

export const KEYS_PAGE_SIZE = 10;

export const KEYS_PAGE_SIZE_OPTIONS: readonly number[] = [10, 25, 50];

export const EXAMPLE_PROJECTS = 5;

export const EXAMPLE_SLUG = 'my-project';

export const KEY_PLACEHOLDER = 'msb_…';

export const NAME_MAX = 120;

export const ADDRESS_PATTERN = /^https?:\/\/\S+$/;

export const POLL_MS = 5000;
