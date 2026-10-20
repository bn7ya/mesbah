import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

import { RESULTS } from './stack';
import type { Role, World } from './world.types';

export const WORLD_FILE = join(RESULTS, 'world.json');

export function stateFile(role: Role): string {
  return join(RESULTS, 'auth', `${role}.json`);
}

function isWorld(value: unknown): value is World {
  return typeof value === 'object' && value !== null && 'users' in value && 'projects' in value;
}

export function readWorld(): World {
  const parsed: unknown = JSON.parse(readFileSync(WORLD_FILE, 'utf8'));
  if (!isWorld(parsed)) {
    throw new Error(`${WORLD_FILE} was not written by the setup journey`);
  }
  return parsed;
}

export function writeWorld(world: World): void {
  writeFileSync(WORLD_FILE, `${JSON.stringify(world, null, 2)}\n`);
}
