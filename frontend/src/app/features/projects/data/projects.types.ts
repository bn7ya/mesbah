import type { ApiError } from '@core/http/api.types';
import type { Role } from '@core/auth/roles.types';
import type { VersionLabel } from '@shared/version/version.types';

export type ProjectKind = 'finetune' | 'scratch';

export type BaseModelFamily = 'dense_decoder' | 'moe_decoder' | 'encoder_decoder' | 'other';

export type BaseModelStatus = 'queued' | 'downloading' | 'ready' | 'failed' | 'cancelled';

export interface Generation {
  readonly temperature: number;
  readonly top_p: number;
  readonly max_tokens: number;
}

export interface ProjectBaseModel {
  readonly id: string;
  readonly repo_id: string;
  readonly family: BaseModelFamily;
  readonly parameters: number | null;
  readonly supports_thinking: boolean;
  readonly status: BaseModelStatus;
}

export interface Project {
  readonly id: string;
  readonly name: string;
  readonly slug: string;
  readonly description: string;
  readonly kind: ProjectKind;
  readonly base_model: ProjectBaseModel | null;
  readonly active_version: VersionLabel | null;
  readonly system_prompt: string;
  readonly thinking: boolean;
  readonly generation: Generation;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface NewProject {
  readonly name: string;
  readonly base_model: string;
  readonly description?: string;
  readonly system_prompt?: string;
  readonly thinking?: boolean;
}

export interface ProjectChange {
  readonly name?: string;
  readonly description?: string;
  readonly system_prompt?: string;
  readonly thinking?: boolean;
  readonly generation?: Generation;
}

export interface LibraryModelWire {
  readonly id: string;
  readonly repo_id: string;
  readonly parameters: number | null;
  readonly supports_thinking: boolean;
  readonly status: BaseModelStatus;
}

export interface ModelOption {
  readonly id: string;
  readonly repo_id: string;
  readonly parameters: number | null;
  readonly supports_thinking: boolean;
}

export interface ProjectTab {
  readonly path: string;
  readonly labelKey: string;
  readonly icon: string;
  readonly role: Role;
}

export interface SliderRange {
  readonly min: number;
  readonly max: number;
  readonly step: number;
}

export type GenerationKey = keyof Generation;

export interface GenerationSetting {
  readonly key: GenerationKey;
  readonly labelKey: string;
  readonly hintKey: string;
  readonly termKey: string;
  readonly range: SliderRange;
  readonly digits: number;
}

export type CreateResult = { readonly project: Project } | { readonly error: ApiError };

export const READY: BaseModelStatus = 'ready';

const TEMPERATURE_RANGE: SliderRange = { min: 0, max: 2, step: 0.05 };

const TOP_P_RANGE: SliderRange = { min: 0, max: 1, step: 0.05 };

const MAX_TOKENS_RANGE: SliderRange = { min: 16, max: 32768, step: 16 };

export const GENERATION_SETTINGS: readonly GenerationSetting[] = [
  {
    key: 'temperature',
    labelKey: 'projects.reply.temperature',
    hintKey: 'projects.reply.temperatureHint',
    termKey: 'temperature',
    range: TEMPERATURE_RANGE,
    digits: 2,
  },
  {
    key: 'top_p',
    labelKey: 'projects.reply.topP',
    hintKey: 'projects.reply.topPHint',
    termKey: 'top_p',
    range: TOP_P_RANGE,
    digits: 2,
  },
  {
    key: 'max_tokens',
    labelKey: 'projects.reply.maxTokens',
    hintKey: 'projects.reply.maxTokensHint',
    termKey: 'token',
    range: MAX_TOKENS_RANGE,
    digits: 0,
  },
];

export const NAME_MAX = 120;

export const DESCRIPTION_MAX = 4000;

export const PROMPT_MAX = 20000;
