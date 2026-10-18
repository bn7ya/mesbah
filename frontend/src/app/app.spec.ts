import { TestBed, type ComponentFixture } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { LocaleStore } from '@core/i18n/locale.store';
import { App } from './app';

describe('App', () => {
  let fixture: ComponentFixture<App>;
  let host: HTMLElement;
  let main: HTMLElement;

  beforeEach(async () => {
    localStorage.clear();
    TestBed.configureTestingModule({ providers: [provideRouter([])] });
    TestBed.inject(LocaleStore).setLocale('en');
    main = document.createElement('main');
    main.id = 'main';
    main.tabIndex = -1;
    document.body.append(main);
    fixture = TestBed.createComponent(App);
    host = fixture.nativeElement as HTMLElement;
    await fixture.whenStable();
  });

  afterEach(() => {
    main.remove();
    TestBed.resetTestingModule();
  });

  it('moves focus to the main content when the skip link is activated', () => {
    const link = host.querySelector<HTMLAnchorElement>('.skip-link')!;

    link.click();

    expect(document.activeElement).toBe(main);
  });

  it('stays on the page: the click is cancelled, so the address does not change', () => {
    const link = host.querySelector<HTMLAnchorElement>('.skip-link')!;
    const click = new MouseEvent('click', { bubbles: true, cancelable: true });

    link.dispatchEvent(click);

    expect(click.defaultPrevented).toBe(true);
    expect(window.location.hash).toBe('');
  });

  it('does nothing when the page has no main content', () => {
    main.remove();

    expect(() => host.querySelector<HTMLAnchorElement>('.skip-link')!.click()).not.toThrow();
  });
});
