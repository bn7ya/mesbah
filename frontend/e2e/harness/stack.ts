import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

import type { Stack } from './stack.types';

export const FRONTEND = resolve(import.meta.dirname, '..', '..');
export const BACKEND = resolve(FRONTEND, '..', 'backend');
export const RESULTS = resolve(process.env['E2E_RESULTS'] ?? join(FRONTEND, 'test-results', 'e2e'));
export const STACK_FILE = process.env['E2E_STACK'] ?? join(RESULTS, 'stack', 'stack.json');
export const PORT = Number(process.env['E2E_PORT'] ?? 8177);

const FIELDS: readonly (keyof Stack)[] = [
  'base_url',
  'engine_url',
  'data_dir',
  'setup_code',
  'version',
  'mesbah_pid',
  'engine_pid',
  'logs',
];

function isStack(value: unknown): value is Stack {
  return typeof value === 'object' && value !== null && FIELDS.every((field) => field in value);
}

export function readStack(path: string = STACK_FILE): Stack {
  const parsed: unknown = JSON.parse(readFileSync(path, 'utf8'));
  if (!isStack(parsed)) {
    throw new Error(`${path} does not describe a running Mesbah`);
  }
  return parsed;
}
