import type { Json } from './api.types';

export interface Expectation {
  readonly status: number;
  readonly code: string | null;
  readonly body?: Json;
  readonly ownSession?: true;
}

export type Expectations = Readonly<Record<string, Expectation>>;
