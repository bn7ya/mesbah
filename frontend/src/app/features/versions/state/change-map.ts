import {
  EVEN_SHARE,
  MAX_TINT,
  TOP_LAYERS,
  type ChangeCell,
  type ChangeGroup,
  type ChangeMap,
  type LayerChange,
  type ModuleKind,
  type VersionChanges,
} from '../data/versions.types';

const ATTENTION: readonly string[] = [
  'q_proj',
  'k_proj',
  'v_proj',
  'o_proj',
  'qkv_proj',
  'query_key_value',
  'c_attn',
  'Wqkv',
  'out_proj',
];

const FEED_FORWARD: readonly string[] = [
  'gate_proj',
  'up_proj',
  'down_proj',
  'gate_up_proj',
  'w1',
  'w2',
  'w3',
  'fc1',
  'fc2',
  'c_fc',
  'dense_h_to_4h',
  'dense_4h_to_h',
];

const KIND_ORDER: readonly ModuleKind[] = ['attention', 'feed_forward', 'other'];

function moduleKind(module: string): ModuleKind {
  if (ATTENTION.includes(module)) {
    return 'attention';
  }
  return FEED_FORWARD.includes(module) ? 'feed_forward' : 'other';
}

function position(module: string): number {
  const known = [...ATTENTION, ...FEED_FORWARD].indexOf(module);
  return known === -1 ? Number.MAX_SAFE_INTEGER : known;
}

function inReadingOrder(modules: readonly string[]): readonly string[] {
  return [...modules].sort((a, b) => {
    const kinds = KIND_ORDER.indexOf(moduleKind(a)) - KIND_ORDER.indexOf(moduleKind(b));
    if (kinds !== 0) {
      return kinds;
    }
    return position(a) - position(b) || a.localeCompare(b);
  });
}

function strength(layer: LayerChange): number {
  return Math.sqrt(Object.values(layer.norms).reduce((sum, norm) => sum + norm * norm, 0));
}

function cell(module: string, norm: number | undefined, largest: number): ChangeCell {
  if (norm === undefined) {
    return { module, norm: null, tint: 0 };
  }
  return { module, norm, tint: largest > 0 ? Math.round((norm / largest) * MAX_TINT) : 0 };
}

function groupsOf(modules: readonly string[], layers: readonly LayerChange[]): readonly ChangeGroup[] {
  return KIND_ORDER.flatMap((kind) => {
    const members = modules.filter((module) => moduleKind(module) === kind);
    const norms = layers.flatMap((layer) =>
      members.flatMap((module) => (layer.norms[module] === undefined ? [] : [layer.norms[module]])),
    );
    const mean = norms.length > 0 ? norms.reduce((sum, norm) => sum + norm, 0) / norms.length : 0;
    return members.length > 0 ? [{ kind, modules: members, mean }] : [];
  });
}

function leadingKind(groups: readonly ChangeGroup[]): ChangeMap['leading'] {
  const compared = groups.filter((group) => group.kind !== 'other').sort((a, b) => b.mean - a.mean);
  if (compared.length < 2 || compared[0].mean <= 0) {
    return null;
  }
  const gap = (compared[0].mean - compared[1].mean) / compared[0].mean;
  return gap < EVEN_SHARE ? 'even' : compared[0].kind;
}

export function buildChangeMap(changes: VersionChanges): ChangeMap {
  const groups = groupsOf(inReadingOrder(changes.modules), changes.layers);
  const modules = groups.flatMap((group) => group.modules);
  const largest = Math.max(0, ...changes.layers.flatMap((layer) => Object.values(layer.norms)));
  const strongest = [...changes.layers]
    .sort((a, b) => strength(b) - strength(a) || a.layer - b.layer)
    .slice(0, TOP_LAYERS)
    .map((layer) => layer.layer);
  return {
    groups,
    modules,
    rows: changes.layers.map((layer) => ({
      layer: layer.layer,
      cells: modules.map((module) => cell(module, layer.norms[module], largest)),
    })),
    topLayers: changes.layers.length > TOP_LAYERS ? strongest : [],
    leading: leadingKind(groups),
  };
}
