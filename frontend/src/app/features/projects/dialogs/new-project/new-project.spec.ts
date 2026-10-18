import { signal } from '@angular/core';
import { TestBed, type ComponentFixture } from '@angular/core/testing';
import { MatDialogRef } from '@angular/material/dialog';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { LocaleStore } from '@core/i18n/locale.store';
import type { CreateResult, ModelOption, NewProject } from '../../data/projects.types';
import ar from '../../i18n/ar.json';
import en from '../../i18n/en.json';
import { ProjectsStore } from '../../state/projects.store';
import { NewProjectDialog } from './new-project';

const MODELS: readonly ModelOption[] = [
  { id: 'm1', repo_id: 'org/one', parameters: 1_000_000_000, supports_thinking: false },
  { id: 'm2', repo_id: 'org/two', parameters: 2_000_000_000, supports_thinking: true },
];

describe('NewProjectDialog', () => {
  const readyModels = signal<readonly ModelOption[]>(MODELS);
  const create = vi.fn<(project: NewProject) => Promise<CreateResult>>();
  const close = vi.fn<(id: string) => void>();

  let fixture: ComponentFixture<NewProjectDialog>;
  let host: HTMLElement;

  const errors = (): string[] => Array.from(host.querySelectorAll('mat-error')).map((error) => error.textContent.trim());

  async function submit(): Promise<void> {
    host.querySelector<HTMLButtonElement>('button[type="submit"]')!.click();
    await fixture.whenStable();
    await fixture.whenStable();
  }

  beforeEach(async () => {
    localStorage.clear();
    create.mockReset();
    close.mockReset();
    readyModels.set(MODELS);
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        {
          provide: ProjectsStore,
          useValue: {
            readyModels,
            modelsLoading: signal(false),
            modelsError: signal(null),
            creating: signal(false),
            modelsAgain: vi.fn(),
            create,
          },
        },
        { provide: MatDialogRef, useValue: { close } },
      ],
    });
    const locale = TestBed.inject(LocaleStore);
    locale.register({ en, ar });
    locale.setLocale('en');
    fixture = TestBed.createComponent(NewProjectDialog);
    host = fixture.nativeElement as HTMLElement;
    await fixture.whenStable();
    const name = host.querySelector<HTMLInputElement>('input[name="name"]')!;
    name.value = 'Support assistant';
    name.dispatchEvent(new Event('input'));
    await fixture.whenStable();
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('says the base model is required when a name is given and no model is chosen', async () => {
    await submit();

    expect(errors()).toEqual(['Choose the base model.']);
    expect(host.querySelector('mat-select')?.getAttribute('aria-invalid')).toBe('true');
    expect(create).not.toHaveBeenCalled();
  });

  it('says so in Arabic too', async () => {
    TestBed.inject(LocaleStore).setLocale('ar');

    await submit();

    expect(errors()).toEqual(['اختر النموذج الأساسي.']);
  });

  it('creates the project once a model is chosen', async () => {
    create.mockResolvedValue({ error: { code: 'unknown', message: 'Nope' } });
    fixture.componentInstance.modelId.set('m2');
    await fixture.whenStable();

    await submit();

    expect(errors()).toEqual([]);
    expect(create).toHaveBeenCalledWith(expect.objectContaining({ name: 'Support assistant', base_model: 'm2' }));
  });
});
