import type { Device } from './serving.types';

const GPU = /^cuda(?::(\d+))?$/;

export function deviceOf(raw: string | null): Device {
  if (raw === null || raw === '') {
    return { kind: 'none', index: null, raw: '' };
  }
  if (raw === 'cpu') {
    return { kind: 'cpu', index: null, raw };
  }
  const gpu = GPU.exec(raw);
  if (gpu !== null) {
    return { kind: 'gpu', index: gpu[1] === undefined ? null : Number(gpu[1]), raw };
  }
  return { kind: 'other', index: null, raw };
}
