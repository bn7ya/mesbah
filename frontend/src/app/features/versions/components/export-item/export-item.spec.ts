import { Clipboard } from '@angular/cdk/clipboard';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { LocaleStore } from '@core/i18n/locale.store';
import type { VersionExport } from '../../data/versions.types';
import ar from '../../i18n/ar.json';
import en from '../../i18n/en.json';
import { VersionsStore } from '../../state/versions.store';
import { ExportItem } from './export-item';

function row(overrides: Partial<VersionExport> = {}): VersionExport {
  return {
    id: 'e1',
    version: 'v1',
    format: 'gguf',
    out_type: 'q8_0',
    status: 'ready',
    error_code: '',
    path: '/data/exports/e1/model.gguf',
    size_bytes: 14_000_000,
    downloadable: true,
    created_at: '2026-10-18T10:00:00Z',
    finished_at: '2026-10-18T10:01:00Z',
    created_by: 'tariq',
    ...overrides,
  };
}

describe('ExportItem', () => {
  const canWrite = signal(true);
  const copy = vi.fn<(text: string) => boolean>(() => true);

  function render(item: VersionExport): HTMLElement {
    const fixture = TestBed.createComponent(ExportItem);
    fixture.componentRef.setInput('item', item);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  beforeEach(() => {
    canWrite.set(true);
    copy.mockClear();
    TestBed.configureTestingModule({
      providers: [
        {
          provide: VersionsStore,
          useValue: {
            canWrite,
            exportsWorking: signal<readonly string[]>([]),
            downloadUrl: (exported: VersionExport) => `/api/versions/exports/${exported.id}/download/`,
          },
        },
        { provide: Clipboard, useValue: { copy } },
      ],
    });
    const locale = TestBed.inject(LocaleStore);
    locale.register({ en, ar });
    locale.setLocale('en');
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('offers a ready GGUF file as a download from the file endpoint', () => {
    const page = render(row());

    const link = page.querySelector('a');
    expect(link?.getAttribute('href')).toBe('/api/versions/exports/e1/download/');
    expect(link?.hasAttribute('download')).toBe(true);
    expect(page.textContent).toContain('Ready');
    expect(page.textContent).toContain('q8_0');
    expect(page.textContent).not.toContain('Copy path');
  });

  it('shows where a merged model is and offers to copy the path, never a download', () => {
    const page = render(
      row({ format: 'merged', out_type: '', downloadable: false, path: '/data/exports/e1/output' }),
    );

    expect(page.querySelector('a')).toBeNull();
    expect(page.querySelector('code')?.textContent).toBe('/data/exports/e1/output');
    expect(page.textContent).toContain('Copy path');
  });

  it('copies the path of a merged model', () => {
    const page = render(row({ format: 'merged', downloadable: false, path: '/data/exports/e1/output' }));

    const button = [...page.querySelectorAll('button')].find((candidate) => candidate.textContent?.includes('Copy path'));
    button?.click();

    expect(copy).toHaveBeenCalledWith('/data/exports/e1/output');
  });

  it.each(['queued', 'running'] as const)('shows a bar while the export is %s, and no download', (status) => {
    const page = render(row({ status, path: '', size_bytes: 0, downloadable: false }));

    expect(page.querySelector('mat-progress-bar')).not.toBeNull();
    expect(page.querySelector('a')).toBeNull();
    expect(page.textContent).not.toContain('Size:');
  });

  it('says why a failed export failed, in words', () => {
    const page = render(row({ status: 'failed', error_code: 'out_of_memory', downloadable: false, path: '' }));

    expect(page.textContent).toContain('Failed');
    expect(page.textContent).toContain(en.versions.exports.failure.out_of_memory);
    expect(page.querySelector('mat-progress-bar')).toBeNull();
  });

  it('reads an unknown failure code as a plain failure', () => {
    const page = render(row({ status: 'failed', error_code: 'something_new', downloadable: false }));

    expect(page.textContent).toContain(en.versions.exports.failure.failed);
  });

  it('hides Remove from a reader who cannot write', () => {
    canWrite.set(false);
    const page = render(row());

    expect(page.textContent).not.toContain('Remove');
    expect(page.querySelector('a')).not.toBeNull();
  });
});
