import {
  EXACT_FIELDS,
  EXPERT_FIELDS,
  EXPERT_ONLY_KEYS,
  FALLBACK_SETTINGS,
  type FieldProblem,
  type Hyperparams,
  type NumberField,
  type Plan,
} from '../data/training.types';

const NUMBER_FIELDS: readonly NumberField[] = [...EXACT_FIELDS, ...EXPERT_FIELDS];

export function settingsFrom(plan: Plan | null): Hyperparams {
  return { ...FALLBACK_SETTINGS, ...plan?.hyperparams };
}

export function problemsOf(settings: Hyperparams): readonly FieldProblem[] {
  const problems: FieldProblem[] = [];
  for (const field of NUMBER_FIELDS) {
    const value: number | null | undefined = settings[field.key] as number | null | undefined;
    if (value === null || value === undefined) {
      if (!field.optional) {
        problems.push({ key: field.key, kind: 'required' });
      }
    } else if (!Number.isFinite(value) || value < field.min || value > field.max) {
      problems.push({ key: field.key, kind: 'range' });
    } else if (field.integer && !Number.isInteger(value)) {
      problems.push({ key: field.key, kind: 'whole' });
    }
  }
  return problems;
}

export function expertChanged(settings: Hyperparams, defaults: Hyperparams): boolean {
  return EXPERT_ONLY_KEYS.some((key) => settings[key] !== defaults[key]);
}

export function resetExpert(settings: Hyperparams, defaults: Hyperparams): Hyperparams {
  const kept: Partial<Hyperparams> = {};
  for (const key of EXPERT_ONLY_KEYS) {
    Object.assign(kept, { [key]: defaults[key] });
  }
  return { ...settings, ...kept };
}
