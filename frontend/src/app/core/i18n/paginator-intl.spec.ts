import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { LocaleStore } from './locale.store';
import { LocalePaginatorIntl } from './paginator-intl';

describe('LocalePaginatorIntl', () => {
  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({ providers: [LocalePaginatorIntl] });
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('labels the paginator in the reader language', () => {
    const intl = TestBed.inject(LocalePaginatorIntl);
    TestBed.tick();

    expect(intl.itemsPerPageLabel).toBe('لكل صفحة:');
    expect(intl.getRangeLabel(1, 25, 60)).toBe('26–50 من 60');
  });

  it('follows a language switch', () => {
    const intl = TestBed.inject(LocalePaginatorIntl);
    TestBed.inject(LocaleStore).setLocale('en');
    TestBed.tick();

    expect(intl.itemsPerPageLabel).toBe('Per page:');
    expect(intl.getRangeLabel(0, 25, 0)).toBe('Nothing to show');
  });
});
