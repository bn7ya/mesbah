import type { UiLocale } from './copy.types';

export type Role = 'owner' | 'reviewer' | 'trainer' | 'viewer';

export interface Seeded {
  readonly chat: string;
  readonly versions: string;
  readonly exports: string;
}

export interface World {
  readonly password: string;
  readonly users: Readonly<Record<Role, string>>;
  readonly baseModel: string;
  readonly dataset: string;
  readonly projects: Readonly<Record<UiLocale, Seeded>>;
}
