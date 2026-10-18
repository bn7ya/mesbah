import { ChangeDetectionStrategy, Component, Injector, computed, inject, output, signal } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatCard } from '@angular/material/card';
import { MatDialog } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatPaginator, type PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { firstValueFrom } from 'rxjs';

import type { ApiError } from '@core/http/api.types';
import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { confirmAction } from '@shared/confirm-dialog/confirm-dialog';
import { CompactPipe } from '@shared/format/compact.pipe';
import { DateTimePipe } from '@shared/format/datetime.pipe';
import type { Draft, Preset, SaveDialogData } from '../../data/architect.types';
import { SaveDraftDialog } from '../../dialogs/save-draft/save-draft';
import { ArchitectStore } from '../../state/architect.store';

@Component({
  selector: 'app-starting-points',
  imports: [CompactPipe, DateTimePipe, MatButton, MatCard, MatIcon, MatPaginator, MatProgressBar, TranslatePipe],
  templateUrl: './starting-points.html',
  styleUrl: './starting-points.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StartingPoints {
  private readonly store = inject(ArchitectStore);
  private readonly dialog = inject(MatDialog);
  private readonly injector = inject(Injector);
  private readonly snackBar = inject(MatSnackBar);
  private readonly locale = inject(LocaleStore);

  readonly chosen = output<void>();

  readonly presets = this.store.presets;
  readonly presetsLoading = this.store.presetsLoading;
  readonly presetsError = this.store.presetsError;
  readonly page = this.store.draftPage;
  readonly pageIndex = this.store.pageIndex;
  readonly pageSize = this.store.pageSize;
  readonly draftsLoading = this.store.draftsLoading;
  readonly draftsError = this.store.draftsError;
  readonly canWrite = this.store.canWrite;
  readonly startedFrom = this.store.startedFrom;
  readonly current = this.store.draft;

  readonly failure = signal<ApiError | null>(null);

  readonly empty = computed(() => this.page().results.length === 0 && !this.draftsLoading() && this.draftsError() === null);
  readonly paged = computed(() => this.page().count > this.pageSize());

  presetName(preset: Preset): string {
    return this.store.presetLabel(preset.name);
  }

  isWorking(draft: Draft): boolean {
    return this.store.working().includes(draft.id);
  }

  presetsAgain(): void {
    this.store.presetsAgain();
  }

  draftsAgain(): void {
    void this.store.loadDrafts();
  }

  turnPage(event: PageEvent): void {
    void this.store.loadDrafts(event.pageIndex, event.pageSize);
  }

  async usePreset(preset: Preset): Promise<void> {
    if (await this.mayReplace()) {
      this.store.usePreset(preset);
      this.chosen.emit();
    }
  }

  async open(draft: Draft): Promise<void> {
    if (await this.mayReplace()) {
      this.store.openDraft(draft);
      this.chosen.emit();
    }
  }

  async rename(draft: Draft): Promise<void> {
    const reference = this.dialog.open<SaveDraftDialog, SaveDialogData, Draft>(SaveDraftDialog, {
      injector: this.injector,
      data: { mode: 'rename', draft },
      width: '30rem',
      maxWidth: '95vw',
      autoFocus: 'first-tabbable',
    });
    if (await firstValueFrom(reference.afterClosed())) {
      this.report('architect.report.renamed');
    }
  }

  async remove(draft: Draft): Promise<void> {
    const confirmed = await confirmAction(this.dialog, {
      titleKey: 'architect.remove.title',
      bodyKey: 'architect.remove.body',
      confirmKey: 'architect.remove.confirm',
      values: { name: draft.name },
      destructive: true,
    });
    if (!confirmed) {
      return;
    }
    const error = await this.store.removeDraft(draft);
    this.failure.set(error);
    if (error === null) {
      this.report('architect.report.removed');
    }
  }

  private async mayReplace(): Promise<boolean> {
    if (!this.store.dirty()) {
      return true;
    }
    return confirmAction(this.dialog, {
      titleKey: 'architect.discard.title',
      bodyKey: 'architect.discard.body',
      confirmKey: 'architect.discard.confirm',
      destructive: true,
    });
  }

  private report(key: string): void {
    this.snackBar.open(this.locale.translate(key), undefined, { duration: 4000 });
  }
}
