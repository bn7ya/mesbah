import { describe, expect, it } from 'vitest';

import { MAX_TINT, type VersionChanges } from '../data/versions.types';
import { buildChangeMap } from './change-map';

function changes(layers: Record<string, number>[], overrides: Partial<VersionChanges> = {}): VersionChanges {
  return {
    version: 'v1',
    modules: [...new Set(layers.flatMap((norms) => Object.keys(norms)))].sort(),
    layers: layers.map((norms, layer) => ({ layer, norms })),
    total_norm: null,
    change_from_parent: null,
    parameters: null,
    rank: null,
    ...overrides,
  };
}

describe('buildChangeMap', () => {
  it('puts attention modules first, then feed-forward, then the rest', () => {
    const map = buildChangeMap(changes([{ down_proj: 1, v_proj: 1, lm_head: 1, gate_proj: 1, q_proj: 1, up_proj: 1 }]));

    expect(map.modules).toEqual(['q_proj', 'v_proj', 'gate_proj', 'up_proj', 'down_proj', 'lm_head']);
    expect(map.groups.map((group) => group.kind)).toEqual(['attention', 'feed_forward', 'other']);
    expect(map.groups[0].modules).toEqual(['q_proj', 'v_proj']);
  });

  it('tints each cell by its share of the largest one, up to the darkest that keeps text readable', () => {
    const map = buildChangeMap(changes([{ q_proj: 1, k_proj: 0.5 }, { q_proj: 0.25, k_proj: 0 }]));

    expect(map.rows[0].cells.map((cell) => cell.tint)).toEqual([MAX_TINT, MAX_TINT / 2]);
    expect(map.rows[1].cells.map((cell) => cell.tint)).toEqual([MAX_TINT / 4, 0]);
  });

  it('keeps a missing module as an empty cell rather than a zero', () => {
    const map = buildChangeMap(changes([{ q_proj: 1, k_proj: 1 }, { q_proj: 1 }]));

    expect(map.rows[1].cells[1]).toEqual({ module: 'k_proj', norm: null, tint: 0 });
  });

  it('names the three layers that changed most, once there are more than three', () => {
    const map = buildChangeMap(changes([{ q_proj: 0.1 }, { q_proj: 0.9 }, { q_proj: 0.5 }, { q_proj: 0.7 }, { q_proj: 0.2 }]));

    expect(map.topLayers).toEqual([1, 3, 2]);
  });

  it('names no layers when three or fewer exist', () => {
    const map = buildChangeMap(changes([{ q_proj: 0.1 }, { q_proj: 0.9 }, { q_proj: 0.5 }]));

    expect(map.topLayers).toEqual([]);
  });

  it('weighs a layer by all its modules together', () => {
    const map = buildChangeMap(
      changes([{ q_proj: 0.6, k_proj: 0.6, v_proj: 0.6 }, { q_proj: 0.9 }, { q_proj: 0.1 }, { q_proj: 0.2 }]),
    );

    expect(map.topLayers[0]).toBe(0);
  });

  it('says which kind of module changed most, comparing averages and not totals', () => {
    const attention = buildChangeMap(changes([{ q_proj: 0.9, k_proj: 0.8, gate_proj: 0.2, up_proj: 0.1, down_proj: 0.1 }]));
    const feed = buildChangeMap(changes([{ q_proj: 0.1, gate_proj: 0.9, up_proj: 0.8 }]));

    expect(attention.leading).toBe('attention');
    expect(feed.leading).toBe('feed_forward');
  });

  it('calls it even when the two kinds are within a tenth of each other', () => {
    const map = buildChangeMap(changes([{ q_proj: 0.5, gate_proj: 0.47 }]));

    expect(map.leading).toBe('even');
  });

  it('compares nothing when only one kind was trained', () => {
    const map = buildChangeMap(changes([{ q_proj: 0.5, v_proj: 0.4 }]));

    expect(map.leading).toBeNull();
  });

  it('draws an empty map for a version with nothing recorded', () => {
    const map = buildChangeMap(changes([]));

    expect(map.rows).toEqual([]);
    expect(map.modules).toEqual([]);
    expect(map.leading).toBeNull();
    expect(map.topLayers).toEqual([]);
  });

  it('does not divide by zero when nothing changed at all', () => {
    const map = buildChangeMap(changes([{ q_proj: 0, gate_proj: 0 }]));

    expect(map.rows[0].cells.map((cell) => cell.tint)).toEqual([0, 0]);
    expect(map.leading).toBeNull();
  });
});
