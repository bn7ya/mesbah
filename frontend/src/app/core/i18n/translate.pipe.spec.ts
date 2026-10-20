import { ChangeDetectionStrategy, Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { LocaleStore } from './locale.store';
import { TranslatePipe } from './translate.pipe';

@Component({
  imports: [TranslatePipe],
  template: `<h1>{{ 'auth.signIn.title' | t }}</h1>`,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
class Host {}

describe('TranslatePipe', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('re-renders already-rendered text when the language changes', async () => {
    const fixture = TestBed.createComponent(Host);
    const store = TestBed.inject(LocaleStore);
    store.setLocale('en');
    await fixture.whenStable();
    const heading = (fixture.nativeElement as HTMLElement).querySelector('h1');
    expect(heading?.textContent).toBe('Sign in');

    store.setLocale('ar');
    await fixture.whenStable();

    expect(heading?.textContent).toBe('تسجيل الدخول');
  });
});
