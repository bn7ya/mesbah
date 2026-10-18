import { Directionality } from '@angular/cdk/bidi';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { LocaleStore } from './locale.store';

describe('LocaleStore', () => {
  let store: LocaleStore;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({});
    store = TestBed.inject(LocaleStore);
  });

  it('resolves a key from the core bundle', () => {
    store.setLocale('en');
    TestBed.tick();

    expect(store.translate('auth.signIn.title')).toBe('Sign in');
  });

  it('starts in Arabic when no language was chosen', () => {
    expect(store.locale()).toBe('ar');
  });

  it('returns the key itself when there is no translation', () => {
    expect(store.translate('nothing.here')).toBe('nothing.here');
  });

  it('interpolates placeholders', () => {
    store.setLocale('en');
    TestBed.tick();

    expect(store.translate('auth.signedInAs', { name: 'Sara' })).toBe('Signed in as Sara');
  });

  it('leaves a placeholder alone when no value is given for it', () => {
    store.setLocale('en');
    TestBed.tick();

    expect(store.translate('auth.signedInAs')).toBe('Signed in as {name}');
  });

  it('switches the whole dictionary with the language', () => {
    store.setLocale('ar');
    TestBed.tick();

    expect(store.translate('auth.signIn.title')).toBe('تسجيل الدخول');
  });

  it('reports Arabic as right-to-left', () => {
    store.setLocale('ar');
    TestBed.tick();

    expect(store.direction()).toBe('rtl');
    expect(store.isRtl()).toBe(true);
  });

  it('writes the language and direction onto the document element', () => {
    store.setLocale('ar');
    TestBed.tick();

    expect(document.documentElement.lang).toBe('ar');
    expect(document.documentElement.dir).toBe('rtl');
  });

  it('turns Material components with the language', () => {
    const directionality = TestBed.inject(Directionality);
    store.setLocale('en');
    TestBed.tick();
    const changes: string[] = [];
    directionality.change.subscribe((direction) => changes.push(direction));

    store.setLocale('ar');
    TestBed.tick();
    expect(directionality.value).toBe('rtl');

    store.setLocale('en');
    TestBed.tick();
    expect(directionality.value).toBe('ltr');
    expect(changes).toEqual(['rtl', 'ltr']);
  });

  it('merges a registered feature bundle into the dictionary', () => {
    store.register({
      en: { orders: { title: 'Orders' } },
      ar: { orders: { title: 'الطلبات' } },
    });

    store.setLocale('en');
    TestBed.tick();
    expect(store.translate('orders.title')).toBe('Orders');

    store.setLocale('ar');
    TestBed.tick();
    expect(store.translate('orders.title')).toBe('الطلبات');
  });
});
