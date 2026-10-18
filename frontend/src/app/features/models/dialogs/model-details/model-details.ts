import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { MatButton } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogRef,
  MatDialogTitle,
} from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { RouterLink } from '@angular/router';

import type { ApiError } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { BytesPipe } from '@shared/format/bytes.pipe';
import { CompactPipe } from '@shared/format/compact.pipe';
import { formatNumber } from '@shared/format/format';
import { Term } from '@shared/term/term';
import { FitVerdict } from '../../components/fit-verdict/fit-verdict';
import { FIT_USES, type InspectionDialogData, type LibraryRef } from '../../data/models.types';
import { ModelsStore } from '../../state/models.store';

function blocksDownload(ref: LibraryRef | null): boolean {
  return ref !== null && ref.status !== 'failed' && ref.status !== 'cancelled';
}

@Component({
  selector: 'app-model-details',
  imports: [
    BytesPipe,
    CompactPipe,
    FitVerdict,
    MatButton,
    MatDialogActions,
    MatDialogClose,
    MatDialogContent,
    MatDialogTitle,
    MatIcon,
    MatProgressBar,
    RouterLink,
    Term,
    TranslatePipe,
  ],
  templateUrl: './model-details.html',
  styleUrl: './model-details.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ModelDetailsDialog {
  private readonly store = inject(ModelsStore);
  private readonly locale = inject(LocaleStore);
  private readonly reference = inject<MatDialogRef<ModelDetailsDialog, boolean>>(MatDialogRef);

  readonly data = inject<InspectionDialogData>(MAT_DIALOG_DATA);

  readonly uses = FIT_USES;

  readonly inspection = this.store.inspection;
  readonly loading = this.store.inspecting;
  readonly loadFailure = this.store.inspectionError;
  readonly canWrite = this.store.canWrite;
  readonly adding = this.store.adding;

  readonly failure = signal<ApiError | null>(null);

  readonly moe = computed(() => this.inspection()?.family === 'moe_decoder');
  readonly noGpu = computed(() => this.inspection()?.fit.chat.verdict === 'cpu_only');

  readonly blocker = computed<string | null>(() => {
    const model = this.inspection();
    if (model === null) {
      return null;
    }
    if (!this.canWrite()) {
      return 'models.details.readOnly';
    }
    if (!model.downloadable) {
      return 'models.details.notDownloadable';
    }
    return blocksDownload(model.in_library) ? 'models.details.inLibrary' : null;
  });

  constructor() {
    this.store.inspect(this.data.repo);
    inject(DestroyRef).onDestroy(() => this.store.stopInspecting());
  }

  count(value: number): string {
    return formatNumber(value, this.locale.locale());
  }

  tryAgain(): void {
    this.store.inspectAgain();
  }

  async download(): Promise<void> {
    this.failure.set(null);
    const failure = await this.store.add(this.data.repo);
    this.failure.set(failure);
    if (failure === null) {
      this.reference.close(true);
    }
  }
}
