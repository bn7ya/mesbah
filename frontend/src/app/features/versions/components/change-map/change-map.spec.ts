import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { LocaleStore } from '@core/i18n/locale.store';
import { MAX_TINT, type ChangeMap } from '../../data/versions.types';
import ar from '../../i18n/ar.json';
import en from '../../i18n/en.json';
import { ChangeMapView } from './change-map';

const MAP: ChangeMap = {
  groups: [
    { kind: 'attention', modules: ['q_proj', 'k_proj'], mean: 0.6 },
    { kind: 'feed_forward', modules: ['down_proj'], mean: 0.2 },
  ],
  modules: ['q_proj', 'k_proj', 'down_proj'],
  rows: [
    {
      layer: 0,
      cells: [
        { module: 'q_proj', norm: 0.96, tint: MAX_TINT },
        { module: 'k_proj', norm: 0.24, tint: 12 },
        { module: 'down_proj', norm: null, tint: 0 },
      ],
    },
    {
      layer: 1,
      cells: [
        { module: 'q_proj', norm: 0.5, tint: 25 },
        { module: 'k_proj', norm: 0.123, tint: 6 },
        { module: 'down_proj', norm: 0.1, tint: 5 },
      ],
    },
  ],
  topLayers: [],
  leading: 'attention',
};

describe('ChangeMapView', () => {
  let page: HTMLElement;

  function render(locale: 'en' | 'ar'): void {
    const store = TestBed.inject(LocaleStore);
    store.register({ en, ar });
    store.setLocale(locale);
    const fixture = TestBed.createComponent(ChangeMapView);
    fixture.componentRef.setInput('map', MAP);
    fixture.detectChanges();
    page = fixture.nativeElement as HTMLElement;
  }

  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('draws a column per module under its kind, and a row per layer', () => {
    render('en');

    const groups = [...page.querySelectorAll('th[scope="colgroup"]')];
    expect(groups.map((group) => [group.textContent?.trim(), group.getAttribute('colspan')])).toEqual([
      ['Attention', '2'],
      ['Feed-forward', '1'],
    ]);
    expect([...page.querySelectorAll('th[scope="col"].map__module')].map((head) => head.textContent?.trim())).toEqual([
      'q_proj',
      'k_proj',
      'down_proj',
    ]);
    expect(page.querySelectorAll('tbody tr')).toHaveLength(2);
  });

  it('tints each cell from its share of the largest', () => {
    render('en');

    const tiles = [...page.querySelectorAll<HTMLElement>('td.map__cell .map__tile')];
    expect(tiles.map((tile) => tile.style.getPropertyValue('--tint'))).toEqual([
      `${MAX_TINT}%`,
      '12%',
      '0%',
      '25%',
      '6%',
      '5%',
    ]);
  });

  it('names every cell for a screen reader and shows its number', () => {
    render('en');

    const cells = [...page.querySelectorAll('td.map__cell')];
    expect(cells[0].getAttribute('aria-label')).toBe('Layer 0, q_proj: 0.96');
    expect(cells[0].textContent?.trim()).toBe('0.96');
    expect(cells[4].getAttribute('aria-label')).toBe('Layer 1, k_proj: 0.12');
  });

  it('says so, in the cell, when a module was not recorded for a layer', () => {
    render('en');

    const cell = page.querySelectorAll('td.map__cell')[2];
    expect(cell.getAttribute('aria-label')).toBe('Layer 0, down_proj: not recorded');
    expect(cell.textContent?.trim()).toBe('–');
  });

  it('reads in Arabic with Latin digits', () => {
    render('ar');

    const cell = page.querySelectorAll('td.map__cell')[0];
    expect(cell.getAttribute('aria-label')).toBe('الطبقة 0، \u2068q_proj\u2069: 0.96');
    expect(page.querySelector('th[scope="colgroup"]')?.textContent?.trim()).toBe('الانتباه');
  });
});
