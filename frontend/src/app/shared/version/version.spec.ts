import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { LocaleStore } from '@core/i18n/locale.store';
import { ActiveVersionChanges } from './active-version-changes';
import type { ActiveVersionChange } from './version.types';
import { VersionNamePipe } from './version-name.pipe';

describe('ActiveVersionChanges', () => {
  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('hands an announcement to whoever listens', () => {
    const changes = TestBed.inject(ActiveVersionChanges);
    const heard: ActiveVersionChange[] = [];
    changes.changes.subscribe((change) => heard.push(change));

    const change: ActiveVersionChange = { projectId: 'p', version: { id: 'v', number: 2, name: 'Friendlier' } };
    changes.announce(change);

    expect(heard).toEqual([change]);
  });

  it('does not replay an old announcement to a late listener', () => {
    const changes = TestBed.inject(ActiveVersionChanges);
    changes.announce({ projectId: 'p', version: { id: 'v', number: 2, name: 'Friendlier' } });

    const heard: ActiveVersionChange[] = [];
    changes.changes.subscribe((change) => heard.push(change));

    expect(heard).toEqual([]);
  });
});

describe('VersionNamePipe', () => {
  let pipe: VersionNamePipe;

  beforeEach(() => {
    localStorage.clear();
    TestBed.runInInjectionContext(() => {
      pipe = new VersionNamePipe();
    });
    TestBed.inject(LocaleStore).setLocale('en');
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('writes the seeded name of a root in words', () => {
    expect(pipe.transform({ number: 0, name: 'base' })).toBe('Base model');
  });

  it('keeps a name somebody chose', () => {
    expect(pipe.transform({ number: 2, name: 'Friendlier' })).toBe('Friendlier');
    expect(pipe.transform({ number: 0, name: 'Original' })).toBe('Original');
  });

  it('keeps a trained version named base as it is', () => {
    expect(pipe.transform({ number: 3, name: 'base' })).toBe('base');
  });
});
