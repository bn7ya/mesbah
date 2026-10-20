import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  Injector,
  computed,
  inject,
  viewChild,
} from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatCard } from '@angular/material/card';
import { MatDialog } from '@angular/material/dialog';
import { MatDivider } from '@angular/material/divider';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { Note } from '@shared/note/note';
import { Breakdown } from '../../components/breakdown/breakdown';
import { DesignerForm } from '../../components/designer-form/designer-form';
import { TrainingMemory } from '../../components/memory/memory';
import { StartingPoints } from '../../components/starting-points/starting-points';
import type { Draft, SaveDialogData, TrainDialogData, TrainStarted } from '../../data/architect.types';
import { SaveDraftDialog } from '../../dialogs/save-draft/save-draft';
import { TrainDialog } from '../../dialogs/train/train';
import { ArchitectStore } from '../../state/architect.store';

@Component({
  selector: 'app-architect-page',
  imports: [
    Breakdown,
    DesignerForm,
    MatButton,
    MatCard,
    MatDivider,
    MatIcon,
    MatProgressBar,
    Note,
    StartingPoints,
    TrainingMemory,
    TranslatePipe,
  ],
  templateUrl: './architect.html',
  styleUrl: './architect.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ArchitectPage {
  private readonly store = inject(ArchitectStore);
  private readonly dialog = inject(MatDialog);
  private readonly injector = inject(Injector);
  private readonly router = inject(Router);
  private readonly snackBar = inject(MatSnackBar);
  private readonly locale = inject(LocaleStore);

  private readonly designHeading = viewChild.required<ElementRef<HTMLElement>>('designHeading');

  readonly estimate = this.store.estimate;
  readonly estimating = this.store.estimating;
  readonly refusalSummary = this.store.refusalSummary;
  readonly draft = this.store.draft;
  readonly startedFrom = this.store.startedFrom;
  readonly dirty = this.store.dirty;
  readonly saving = this.store.saving;
  readonly canWrite = this.store.canWrite;
  readonly canSave = this.store.canSave;
  readonly canTrain = this.store.canTrain;
  readonly trainBlocker = this.store.trainBlocker;

  readonly startedLabel = computed(() => {
    const name = this.startedFrom();
    return name === null ? null : this.store.presetLabel(name);
  });

  constructor() {
    void this.store.visit();
  }

  focusDesign(): void {
    this.designHeading().nativeElement.focus();
  }

  estimateAgain(): void {
    this.store.estimateAgain();
  }

  async save(): Promise<void> {
    const reference = this.dialog.open<SaveDraftDialog, SaveDialogData, Draft>(SaveDraftDialog, {
      injector: this.injector,
      data: { mode: 'save', draft: this.draft() },
      width: '30rem',
      maxWidth: '95vw',
      autoFocus: 'first-tabbable',
    });
    if (await firstValueFrom(reference.afterClosed())) {
      this.report('architect.report.saved');
    }
  }

  async train(): Promise<void> {
    const draft = this.draft();
    if (draft === null) {
      return;
    }
    const reference = this.dialog.open<TrainDialog, TrainDialogData, TrainStarted>(TrainDialog, {
      injector: this.injector,
      data: { draft },
      width: '38rem',
      maxWidth: '95vw',
      autoFocus: 'first-tabbable',
    });
    const started = await firstValueFrom(reference.afterClosed());
    if (started) {
      this.report('architect.train.started');
      await this.router.navigate(['/projects', started.project, 'training', started.run]);
    }
  }

  private report(key: string): void {
    this.snackBar.open(this.locale.translate(key), undefined, { duration: 4000 });
  }
}
