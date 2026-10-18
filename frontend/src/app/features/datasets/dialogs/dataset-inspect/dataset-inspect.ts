import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, linkedSignal, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import type { ErrorStateMatcher } from '@angular/material/core';
import { MatChip, MatChipSet } from '@angular/material/chips';
import {
  MAT_DIALOG_DATA,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogRef,
  MatDialogTitle,
} from '@angular/material/dialog';
import { MatError, MatFormField, MatHint, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSlideToggle } from '@angular/material/slide-toggle';
import { RouterLink } from '@angular/router';

import type { ApiError } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { CompactPipe } from '@shared/format/compact.pipe';
import { formatNumber } from '@shared/format/format';
import { Term } from '@shared/term/term';
import { DatasetConversation } from '../../components/conversation/conversation';
import {
  COLUMN_ROLES,
  DEFAULT_ROW_LIMIT,
  FORMAT_ICONS,
  MAX_ROW_LIMIT,
  type ChosenColumns,
  type ColumnRole,
  type HubConfig,
  type InspectDialogData,
  type Inspection,
} from '../../data/datasets.types';
import { LanguagesPipe } from '../../pipes/languages.pipe';
import { DatasetsStore } from '../../state/datasets.store';

const PREFERRED_SPLIT = 'train';

@Component({
  selector: 'app-dataset-inspect',
  imports: [
    CompactPipe,
    DatasetConversation,
    FormsModule,
    LanguagesPipe,
    MatButton,
    MatChip,
    MatChipSet,
    MatDialogActions,
    MatDialogClose,
    MatDialogContent,
    MatDialogTitle,
    MatError,
    MatFormField,
    MatHint,
    MatIcon,
    MatInput,
    MatLabel,
    MatOption,
    MatProgressBar,
    MatSelect,
    MatSlideToggle,
    RouterLink,
    Term,
    TranslatePipe,
  ],
  templateUrl: './dataset-inspect.html',
  styleUrl: './dataset-inspect.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DatasetInspectDialog {
  private readonly store = inject(DatasetsStore);
  private readonly locale = inject(LocaleStore);
  private readonly reference = inject<MatDialogRef<DatasetInspectDialog, boolean>>(MatDialogRef);

  readonly data = inject<InspectDialogData>(MAT_DIALOG_DATA);

  readonly roles = COLUMN_ROLES;
  readonly icons = FORMAT_ICONS;
  readonly maxRows = MAX_ROW_LIMIT;

  readonly loading = this.store.inspecting;
  readonly loadFailure = this.store.inspectionError;
  readonly canWrite = this.store.canWrite;
  readonly importing = this.store.importing;

  readonly shown = linkedSignal<Inspection | null, Inspection | null>({
    source: this.store.inspection,
    computation: (next, previous) => next ?? previous?.value ?? null,
  });

  readonly choosing = signal(false);
  readonly columns = signal<ChosenColumns>({ prompt: '', reply: '', thinking: '' });
  readonly rowLimit = signal<number | null>(DEFAULT_ROW_LIMIT);
  readonly failure = signal<ApiError | null>(null);

  readonly unsupported = computed(() => this.shown()?.detected === 'unsupported');
  readonly picking = computed(() => this.choosing() || this.unsupported());
  readonly currentConfig = computed<HubConfig | null>(() => {
    const view = this.shown();
    return view?.configs.find((config) => config.name === view.config) ?? null;
  });
  readonly limitInvalid = computed(() => {
    const limit = this.rowLimit();
    return limit === null || !Number.isInteger(limit) || limit < 1 || limit > MAX_ROW_LIMIT;
  });
  readonly limitErrors: ErrorStateMatcher = { isErrorState: () => this.limitInvalid() };

  readonly blocker = computed<string | null>(() => {
    const view = this.shown();
    if (view === null || this.loading()) {
      return null;
    }
    if (!this.canWrite()) {
      return 'datasets.inspect.readOnly';
    }
    if (view.mapping.format === 'unsupported') {
      return 'datasets.inspect.chooseFirst';
    }
    return view.conversations.length === 0 ? 'datasets.inspect.nothingUsable' : null;
  });

  constructor() {
    this.store.inspect({ repo: this.data.repo });
    inject(DestroyRef).onDestroy(() => this.store.stopInspecting());
  }

  count(value: number): string {
    return formatNumber(value, this.locale.locale());
  }

  chooseConfig(name: string): void {
    const config = this.shown()?.configs.find((entry) => entry.name === name);
    const split = config?.splits.find((entry) => entry.name === PREFERRED_SPLIT) ?? config?.splits[0];
    this.reinspect(name, split?.name ?? '');
  }

  chooseSplit(name: string): void {
    this.reinspect(this.shown()?.config ?? '', name);
  }

  togglePicking(on: boolean): void {
    this.choosing.set(on);
    const mapping = this.shown()?.mapping;
    if (on && mapping) {
      this.columns.set({ prompt: mapping.prompt, reply: mapping.reply, thinking: mapping.thinking });
    }
    if (!on) {
      this.columns.set({ prompt: '', reply: '', thinking: '' });
      this.reinspect(this.shown()?.config ?? '', this.shown()?.split ?? '');
    }
  }

  chooseColumn(role: ColumnRole, column: string): void {
    this.columns.update((current) => ({ ...current, [role]: column }));
    const view = this.shown();
    if (view !== null) {
      this.reinspect(view.config, view.split);
    }
  }

  tryAgain(): void {
    this.store.inspectAgain();
  }

  async startImport(): Promise<void> {
    const view = this.shown();
    const limit = this.rowLimit();
    if (view === null || limit === null || this.limitInvalid()) {
      return;
    }
    this.failure.set(null);
    const failure = await this.store.startImport({
      repo_id: view.repo_id,
      config: view.config,
      split: view.split,
      row_limit: limit,
      mapping: view.mapping,
    });
    this.failure.set(failure);
    if (failure === null) {
      this.reference.close(true);
    }
  }

  private reinspect(config: string, split: string): void {
    const chosen = this.columns();
    const ready = this.picking() && chosen.prompt !== '' && chosen.reply !== '';
    this.store.inspect({ repo: this.data.repo, config, split, columns: ready ? chosen : undefined });
  }
}
