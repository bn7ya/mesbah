import type { RunSource, SourceNames } from '../data/training.types';

export function sourcesOf(ids: readonly string[], names: SourceNames | null): readonly RunSource[] | null {
  return names === null ? null : ids.map((id) => ({ id, name: names[id] ?? null }));
}
