import { describe, expect, it } from 'vitest';

import { highestRole, rolesFrom } from './roles';

describe('roles', () => {
  it('lists a role and every role above it', () => {
    expect(rolesFrom('reviewers')).toEqual(['reviewers', 'trainers', 'admins']);
  });

  it('takes the highest role a user holds', () => {
    expect(highestRole(['viewers', 'trainers'], false)).toBe('trainers');
  });

  it('treats the owner as an administrator', () => {
    expect(highestRole([], true)).toBe('admins');
  });

  it('has no role without a group', () => {
    expect(highestRole([], false)).toBeNull();
  });
});
