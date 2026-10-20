import { describe, expect, it } from 'vitest';

import { sourcesOf } from './run-sources';

describe('sourcesOf', () => {
  it('has nothing to name until the projects are known', () => {
    expect(sourcesOf(['pa', 'pb'], null)).toBeNull();
  });

  it('pairs each project with its name, in the order the run lists them', () => {
    expect(sourcesOf(['pb', 'pa'], { pa: 'Support', pb: 'Engine check' })).toEqual([
      { id: 'pb', name: 'Engine check' },
      { id: 'pa', name: 'Support' },
    ]);
  });

  it('marks a project that can no longer be read with no name', () => {
    expect(sourcesOf(['pa', 'pb'], { pa: 'Support' })).toEqual([
      { id: 'pa', name: 'Support' },
      { id: 'pb', name: null },
    ]);
  });
});
