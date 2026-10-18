import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { LocaleStore } from '@core/i18n/locale.store';
import {
  FALLBACK_SETTINGS,
  type LibraryDataset,
  type Plan,
  type StartVersion,
} from '../../data/training.types';
import ar from '../../i18n/ar.json';
import en from '../../i18n/en.json';
import { TrainingStore } from '../../state/training.store';
import { TrainForm } from './train-form';

const PLAN: Plan = {
  hyperparams: FALLBACK_SETTINGS,
  corrections: 7,
  fit: { verdict: 'cpu_only', required_bytes: 4_000_000_000, available_bytes: 0 },
  gpu_indices: [],
};

const ROOT: StartVersion = { id: 'v0', number: 0, name: 'base', isActive: true };

describe('TrainForm', () => {
  const versions = signal<readonly StartVersion[]>([ROOT]);
  const noModel = signal(false);
  const plan = signal<Plan | null>(PLAN);

  function render(locale: 'en' | 'ar' = 'en'): HTMLElement {
    TestBed.inject(LocaleStore).setLocale(locale);
    const fixture = TestBed.createComponent(TrainForm);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  beforeEach(() => {
    localStorage.clear();
    versions.set([ROOT]);
    noModel.set(false);
    plan.set(PLAN);
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        {
          provide: TrainingStore,
          useValue: {
            projectId: signal('p1'),
            plan,
            planLoading: signal(false),
            versions,
            datasets: signal<readonly LibraryDataset[]>([]),
            datasetsLoading: signal(false),
            starting: signal(false),
            noModel,
          },
        },
      ],
    });
    TestBed.inject(LocaleStore).register({ en, ar });
  });

  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('offers the project versions to start from once the project has a model', () => {
    const form = render();

    expect(form.querySelector('form')).not.toBeNull();
    expect(form.querySelector('button[type="submit"]')?.textContent).toContain('Start training');
    expect(form.textContent).not.toContain('has no model yet');
  });

  it('says training needs the first run to finish while the project has no model', () => {
    versions.set([]);
    noModel.set(true);
    const form = render();

    expect(form.textContent).toContain('Train a new version');
    expect(form.querySelector('[role="status"]')?.textContent).toContain(
      'This project has no model yet. A new version can be trained once its first run has finished.',
    );
    expect(form.querySelector('form')).toBeNull();
    expect(form.querySelector('button[type="submit"]')).toBeNull();
  });

  it('says it in Arabic', () => {
    versions.set([]);
    noModel.set(true);
    const form = render('ar');

    expect(form.querySelector('[role="status"]')?.textContent).toContain('لا يوجد نموذج في هذا المشروع بعد');
  });
});
