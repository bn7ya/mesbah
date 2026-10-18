import { Injectable, computed, inject, signal } from '@angular/core';
import { rxResource, takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import {
  catchError,
  debounceTime,
  firstValueFrom,
  from,
  map,
  mergeMap,
  of,
  switchMap,
  tap,
  toArray,
  type Observable,
} from 'rxjs';

import { rolesFrom } from '@core/auth/roles';
import { AuthStore } from '@core/auth/state/auth.store';
import { EMPTY_PAGE, type ApiError, type Page } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import { formatNumber, isolateLtr } from '@shared/format/format';
import { ArchitectApi } from '../data/architect.api';
import {
  DEFAULT_BLUEPRINT,
  DRAFTS_PAGE_SIZE,
  LIMITS,
  NUMBER_KEYS,
  SOURCES_PAGE_SIZE,
  type Blueprint,
  type DatasetChoice,
  type DatasetOption,
  type Draft,
  type DraftText,
  type Estimate,
  type EstimateOutcome,
  type Family,
  type NumberKey,
  type Preset,
  type RaisedVocabulary,
  type SaveResult,
  type Source,
  type TrainResult,
} from '../data/architect.types';
import { estimateRequest, raisedVocabulary, signature, withinLimit } from '../data/blueprint';

const ESTIMATE_DEBOUNCE_MS = 400;
const PLAN_REQUESTS_AT_ONCE = 6;
const SIZING_KEYS: readonly NumberKey[] = ['seq_len', 'batch'];

function isNumberKey(field: string): field is NumberKey {
  return NUMBER_KEYS.some((key) => key === field);
}

@Injectable()
export class ArchitectStore {
  private readonly api = inject(ArchitectApi);
  private readonly auth = inject(AuthStore);
  private readonly locale = inject(LocaleStore);

  readonly blueprint = signal<Blueprint>(DEFAULT_BLUEPRINT);
  readonly draft = signal<Draft | null>(null);
  readonly startedFrom = signal<string | null>(null);

  readonly estimate = signal<Estimate | null>(null);
  readonly estimating = signal(true);
  readonly refusal = signal<ApiError | null>(null);

  readonly draftPage = signal<Page<Draft>>(EMPTY_PAGE);
  readonly pageIndex = signal(0);
  readonly pageSize = signal(DRAFTS_PAGE_SIZE);
  readonly draftsLoading = signal(false);
  readonly draftsError = signal<ApiError | null>(null);
  readonly working = signal<readonly string[]>([]);

  readonly saving = signal(false);
  readonly training = signal(false);

  readonly sources = signal<readonly Source[]>([]);
  readonly datasets = signal<readonly DatasetOption[]>([]);
  readonly sourcesLoading = signal(false);
  readonly sourcesError = signal<ApiError | null>(null);

  private readonly attempt = signal(0);
  private readonly raised = signal<RaisedVocabulary | null>(null);

  private readonly presetResource = rxResource({ stream: () => this.api.presets() });

  readonly presets = computed<readonly Preset[]>(() => (this.presetResource.hasValue() ? this.presetResource.value() : []));
  readonly presetsLoading = computed(() => this.presetResource.isLoading());
  readonly presetsError = computed(() =>
    this.failure(this.presetResource.status() === 'error' ? this.presetResource.error() : undefined),
  );

  readonly canWrite = computed(() => this.auth.hasAnyGroup(rolesFrom('trainers')));

  readonly family = computed<Family>(() => this.blueprint().family);

  readonly dirty = computed(() => {
    const saved = this.draft();
    return saved !== null && signature(saved.blueprint) !== signature(this.blueprint());
  });

  readonly fieldErrors = computed<Readonly<Partial<Record<NumberKey, string>>>>(() => {
    const errors: Partial<Record<NumberKey, string>> = {};
    const blueprint = this.blueprint();
    for (const key of SIZING_KEYS) {
      if (!withinLimit(blueprint[key], key)) {
        errors[key] = this.sizingMessage(key, blueprint[key] === null);
      }
    }
    const refusal = this.refusal();
    if (refusal !== null) {
      for (const field of Object.keys(refusal.fields ?? {})) {
        if (isNumberKey(field)) {
          errors[field] = this.fieldMessage(refusal, field);
        }
      }
    }
    return errors;
  });

  readonly refusalSummary = computed<ApiError | null>(() => {
    const refusal = this.refusal();
    if (refusal === null) {
      return null;
    }
    const placed = Object.keys(refusal.fields ?? {}).some(isNumberKey);
    return placed ? null : refusal;
  });

  readonly vocabularyNote = computed<string | null>(() => {
    const raised = this.raised();
    if (raised === null) {
      return null;
    }
    return this.locale.translate('architect.vocabulary.raised', {
      tokenizer: isolateLtr(raised.tokenizer),
      tokens: formatNumber(raised.tokens, this.locale.locale()),
    });
  });

  readonly hasFieldErrors = computed(() => Object.keys(this.fieldErrors()).length > 0);

  readonly canSave = computed(
    () => this.canWrite() && this.estimate() !== null && !this.estimating() && !this.hasFieldErrors() && !this.saving(),
  );

  readonly trainBlocker = computed<string | null>(() => {
    const saved = this.draft();
    if (saved === null) {
      return 'architect.train.needSaved';
    }
    if (this.dirty()) {
      return 'architect.train.needSaving';
    }
    return saved.blueprint.tokenizer.trim() === '' ? 'architect.train.needTokenizer' : null;
  });

  readonly canTrain = computed(() => this.canWrite() && this.trainBlocker() === null);

  private readonly request = computed(() => {
    this.attempt();
    return estimateRequest(this.blueprint());
  });

  constructor() {
    toObservable(this.request)
      .pipe(
        tap(() => this.estimating.set(true)),
        debounceTime(ESTIMATE_DEBOUNCE_MS),
        switchMap((request): Observable<EstimateOutcome> => {
          if (request === null) {
            return of({ kind: 'blocked' });
          }
          return this.api.estimate(request).pipe(
            map((estimate): EstimateOutcome => ({ kind: 'estimate', estimate, request })),
            catchError((error: ApiError) => of<EstimateOutcome>({ kind: 'refusal', error })),
          );
        }),
        takeUntilDestroyed(),
      )
      .subscribe((outcome) => this.settle(outcome));
  }

  presetLabel(name: string): string {
    const key = `architect.preset.${name}`;
    const label = this.locale.translate(key);
    return label === key ? name : label;
  }

  setFamily(family: Family): void {
    this.blueprint.update((current) => ({ ...current, family }));
  }

  setNumber(key: NumberKey, value: number | null): void {
    this.blueprint.update((current) => ({ ...current, [key]: value }));
  }

  setTokenizer(tokenizer: string): void {
    this.blueprint.update((current) => ({ ...current, tokenizer }));
  }

  setTied(tied: boolean): void {
    this.blueprint.update((current) => ({ ...current, tie_embeddings: tied }));
  }

  estimateAgain(): void {
    this.attempt.update((count) => count + 1);
  }

  presetsAgain(): void {
    this.presetResource.reload();
  }

  usePreset(preset: Preset): void {
    const current = this.blueprint();
    this.blueprint.set({
      ...preset.blueprint,
      tokenizer: current.tokenizer,
      seq_len: current.seq_len ?? preset.blueprint.seq_len,
      batch: current.batch ?? preset.blueprint.batch,
    });
    this.draft.set(null);
    this.startedFrom.set(preset.name);
  }

  openDraft(draft: Draft): void {
    this.blueprint.set(draft.blueprint);
    this.draft.set(draft);
    this.startedFrom.set(null);
  }

  visit(): Promise<void> {
    this.draftPage.set(EMPTY_PAGE);
    return this.loadDrafts(0);
  }

  async loadDrafts(pageIndex = this.pageIndex(), pageSize = this.pageSize()): Promise<void> {
    this.draftsLoading.set(true);
    this.draftsError.set(null);
    try {
      await this.fetchDrafts(pageIndex, pageSize);
    } catch (error) {
      this.draftsError.set(error as ApiError);
    } finally {
      this.draftsLoading.set(false);
    }
  }

  async save(text: DraftText): Promise<SaveResult> {
    this.saving.set(true);
    try {
      const current = this.draft();
      const blueprint = this.blueprint();
      const saved = await firstValueFrom(
        current === null ? this.api.createDraft(text, blueprint) : this.api.changeDraft(current.id, text, blueprint),
      );
      this.draft.set({ ...saved, blueprint });
      this.startedFrom.set(null);
      await this.refreshDrafts();
      return { draft: saved };
    } catch (error) {
      return { error: error as ApiError };
    } finally {
      this.saving.set(false);
    }
  }

  async rename(draft: Draft, text: DraftText): Promise<SaveResult> {
    this.saving.set(true);
    try {
      const renamed = await firstValueFrom(this.api.changeDraft(draft.id, text, null));
      const open = this.draft();
      if (open?.id === renamed.id) {
        this.draft.set({ ...renamed, blueprint: open.blueprint });
      }
      await this.refreshDrafts();
      return { draft: renamed };
    } catch (error) {
      return { error: error as ApiError };
    } finally {
      this.saving.set(false);
    }
  }

  async removeDraft(draft: Draft): Promise<ApiError | null> {
    this.working.update((ids) => [...ids, draft.id]);
    try {
      await firstValueFrom(this.api.removeDraft(draft.id));
      if (this.draft()?.id === draft.id) {
        this.draft.set(null);
      }
      await this.fetchDrafts(this.indexAfterRemoval(), this.pageSize());
      return null;
    } catch (error) {
      return error as ApiError;
    } finally {
      this.working.update((ids) => ids.filter((id) => id !== draft.id));
    }
  }

  async loadSources(): Promise<void> {
    this.sourcesLoading.set(true);
    this.sourcesError.set(null);
    try {
      const [projects, datasets] = await Promise.all([
        firstValueFrom(this.api.projects(SOURCES_PAGE_SIZE)),
        firstValueFrom(this.api.datasets(SOURCES_PAGE_SIZE)),
      ]);
      const counted = await firstValueFrom(
        from(projects).pipe(
          mergeMap(
            (project) =>
              this.api.corrections(project.id).pipe(
                map((corrections): number | null => corrections),
                catchError(() => of(null)),
                map((corrections) => ({ id: project.id, corrections })),
              ),
            PLAN_REQUESTS_AT_ONCE,
          ),
          toArray(),
        ),
      );
      const byId = new Map(counted.map((row) => [row.id, row.corrections]));
      this.sources.set(projects.map((project) => ({ ...project, corrections: byId.get(project.id) ?? null })));
      this.datasets.set(datasets);
    } catch (error) {
      this.sourcesError.set(error as ApiError);
    } finally {
      this.sourcesLoading.set(false);
    }
  }

  async train(
    draft: Draft,
    name: string,
    projectIds: readonly string[],
    datasets: readonly DatasetChoice[],
  ): Promise<TrainResult> {
    this.training.set(true);
    try {
      const started = await firstValueFrom(
        this.api.train(draft.id, { name, corrections_from: projectIds, datasets }),
      );
      return { started };
    } catch (error) {
      return { error: error as ApiError };
    } finally {
      this.training.set(false);
    }
  }

  private settle(outcome: EstimateOutcome): void {
    this.estimate.set(outcome.kind === 'estimate' ? outcome.estimate : null);
    this.raised.set(outcome.kind === 'estimate' ? raisedVocabulary(outcome.request, outcome.estimate.tokenizer_vocabulary) : null);
    this.refusal.set(outcome.kind === 'refusal' ? outcome.error : null);
    this.estimating.set(false);
  }

  private async fetchDrafts(pageIndex: number, pageSize: number): Promise<void> {
    this.draftPage.set(await firstValueFrom(this.api.drafts({ page: pageIndex + 1, page_size: pageSize })));
    this.pageIndex.set(pageIndex);
    this.pageSize.set(pageSize);
  }

  private async refreshDrafts(): Promise<void> {
    try {
      await this.fetchDrafts(this.pageIndex(), this.pageSize());
    } catch (error) {
      this.draftsError.set(error as ApiError);
    }
  }

  private indexAfterRemoval(): number {
    const remaining = this.draftPage().count - 1;
    const lastIndex = Math.max(0, Math.ceil(remaining / this.pageSize()) - 1);
    return Math.min(this.pageIndex(), lastIndex);
  }

  private sizingMessage(key: NumberKey, missing: boolean): string {
    return missing ? this.locale.translate('errors.design_missing') : this.rangeMessage(key);
  }

  private rangeMessage(key: NumberKey): string {
    const { min, max } = LIMITS[key];
    const language = this.locale.locale();
    return this.locale.translate('architect.error.range', {
      min: formatNumber(min, language),
      max: formatNumber(max, language),
    });
  }

  private fieldMessage(refusal: ApiError, field: NumberKey): string {
    if (refusal.code === 'design_out_of_range') {
      return this.rangeMessage(field);
    }
    if (refusal.code === 'design_not_divisible' && field === 'kv_heads') {
      return this.locale.translate('architect.error.kvNotDivisible');
    }
    return refusal.message;
  }

  private failure(error: Error | undefined): ApiError | null {
    if (error === undefined) {
      return null;
    }
    return (error.cause as ApiError | undefined) ?? { code: 'unknown', message: this.locale.translate('errors.generic') };
  }
}
