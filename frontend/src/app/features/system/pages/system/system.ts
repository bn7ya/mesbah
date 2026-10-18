import { ChangeDetectionStrategy, Component, computed, inject, linkedSignal, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import { MatCard } from '@angular/material/card';
import type { ErrorStateMatcher } from '@angular/material/core';
import { MatDialog } from '@angular/material/dialog';
import { MatError, MatFormField, MatHint, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatListItemLine, MatListItemTitle, MatListOption, MatSelectionList, type MatSelectionListChange } from '@angular/material/list';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { UiModeStore } from '@core/ui/ui-mode.store';
import { confirmAction } from '@shared/confirm-dialog/confirm-dialog';
import { BytesPipe } from '@shared/format/bytes.pipe';
import { Meter } from '@shared/meter/meter';
import type { MeterSegment } from '@shared/meter/meter.types';
import { Term } from '@shared/term/term';
import type { Gpu } from '../../data/system.types';
import { SystemStore } from '../../state/system.store';

const TRAIN_INSTALL = 'pip install "mesbah[train]"';
const CUDA_INSTALL = 'pip install --force-reinstall torch --index-url https://download.pytorch.org/whl/cu130';

@Component({
  selector: 'app-system-page',
  imports: [
    BytesPipe,
    FormsModule,
    MatButton,
    MatCard,
    MatError,
    MatFormField,
    MatHint,
    MatIcon,
    MatInput,
    MatLabel,
    MatListItemLine,
    MatListItemTitle,
    MatListOption,
    MatProgressBar,
    MatSelectionList,
    Meter,
    Term,
    TranslatePipe,
  ],
  templateUrl: './system.html',
  styleUrl: './system.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SystemPage {
  private readonly store = inject(SystemStore);
  private readonly locale = inject(LocaleStore);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  readonly expert = inject(UiModeStore).expert;

  readonly overview = this.store.overview;
  readonly loading = this.store.loading;
  readonly saving = this.store.saving;
  readonly error = this.store.error;
  readonly canManage = this.store.canManage;
  readonly gpus = this.store.gpus;
  readonly selectedGpus = this.store.selectedGpus;
  readonly trainingReady = this.store.trainingReady;
  readonly torchWithoutCuda = this.store.torchWithoutCuda;

  readonly trainInstall = TRAIN_INSTALL;
  readonly cudaInstall = CUDA_INSTALL;

  readonly picked = linkedSignal<readonly number[]>(() => this.overview()?.selected_gpus ?? []);
  readonly pickedNone = computed(() => this.picked().length === 0);

  readonly selectedNames = computed(() => this.selectedGpus().map((gpu) => gpu.name).join(' · '));

  readonly diskSegments = computed<readonly MeterSegment[]>(() => {
    const storage = this.overview()?.storage;
    if (!storage) {
      return [];
    }
    return [
      {
        label: this.locale.translate('system.memory.used'),
        bytes: storage.total_bytes - storage.free_bytes,
        tone: 'secondary',
      },
    ];
  });

  readonly token = signal('');
  readonly tokenSubmitted = signal(false);
  readonly tokenInvalid = computed(() => this.tokenSubmitted() && this.token().trim() === '');
  readonly tokenErrors: ErrorStateMatcher = { isErrorState: () => this.tokenInvalid() };

  constructor() {
    void this.store.load();
  }

  isPicked(gpu: Gpu): boolean {
    return this.picked().includes(gpu.index);
  }

  pick(change: MatSelectionListChange): void {
    this.picked.set(change.source.selectedOptions.selected.map((option) => option.value as number));
  }

  async useGpus(): Promise<void> {
    if (this.pickedNone()) {
      return;
    }
    if (await this.store.selectGpus(this.picked())) {
      this.report('system.gpus.saved');
    }
  }

  async chooseAutomatically(): Promise<void> {
    if (await this.store.selectGpus([])) {
      this.report('system.gpus.saved');
    }
  }

  async saveToken(): Promise<void> {
    this.tokenSubmitted.set(true);
    if (this.tokenInvalid()) {
      return;
    }
    if (await this.store.saveHuggingFaceToken(this.token().trim())) {
      this.token.set('');
      this.tokenSubmitted.set(false);
      this.report('system.hf.saved');
    }
  }

  async removeToken(): Promise<void> {
    const confirmed = await confirmAction(this.dialog, {
      titleKey: 'system.hf.removeTitle',
      bodyKey: 'system.hf.removeBody',
      confirmKey: 'system.hf.remove',
      destructive: true,
    });
    if (confirmed && (await this.store.removeHuggingFaceToken())) {
      this.report('system.hf.removed');
    }
  }

  private report(key: string): void {
    this.snackBar.open(this.locale.translate(key), undefined, { duration: 4000 });
  }
}
