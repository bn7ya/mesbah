import type { Method } from './api.types';

export interface Answer {
  readonly status: number;
  readonly code: string | null;
  readonly message: string;
}

export interface Operation {
  readonly id: string;
  readonly method: Method;
  readonly path: string;
  readonly url: string;
  readonly multipart: boolean;
}
