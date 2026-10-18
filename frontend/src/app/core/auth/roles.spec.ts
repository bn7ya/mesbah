import { describe, expect, it } from 'vitest';

import { rolesFrom } from './roles';

describe('roles', () => {
  it('lists a role and every role above it', () => {
    expect(rolesFrom('reviewers')).toEqual(['reviewers', 'trainers', 'admins']);
  });
});
