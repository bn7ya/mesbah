import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatCard } from '@angular/material/card';
import { MatDialog } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatSnackBar } from '@angular/material/snack-bar';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { confirmAction } from '@shared/confirm-dialog/confirm-dialog';
import { Term } from '@shared/term/term';
import { deviceOf } from '../../data/device';
import { START_COMMANDS, type Engine } from '../../data/serving.types';
import { ServingStore } from '../../state/serving.store';
import { CodeBlock } from '../code-block/code-block';
import { LoadedVersions } from '../loaded-versions/loaded-versions';

@Component({
  selector: 'app-builtin-engine',
  imports: [CodeBlock, LoadedVersions, MatButton, MatCard, MatIcon, Term, TranslatePipe],
  templateUrl: './builtin-engine.html',
  styleUrl: './builtin-engine.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BuiltinEngine {
  private readonly store = inject(ServingStore);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);
  private readonly locale = inject(LocaleStore);

  readonly engine = input.required<Engine>();

  readonly commands = START_COMMANDS;

  readonly state = computed(() => this.engine().state);
  readonly device = computed(() => deviceOf(this.state().device));
  readonly working = computed(() => this.store.working().includes(this.engine().id));
  readonly canFree = computed(() => this.store.canTrain() && this.state().running && this.state().loaded);
  readonly canMakeDefault = computed(() => this.store.canManage() && !this.engine().is_default);

  async free(): Promise<void> {
    const confirmed = await confirmAction(this.dialog, {
      titleKey: 'serving.builtin.free.title',
      bodyKey: 'serving.builtin.free.body',
      confirmKey: 'serving.builtin.free.confirm',
    });
    if (confirmed && (await this.store.unload(this.engine()))) {
      this.report('serving.builtin.free.done');
    }
  }

  async makeDefault(): Promise<void> {
    if (await this.store.change(this.engine(), { is_default: true })) {
      this.report('serving.builtin.madeDefault');
    }
  }

  private report(key: string): void {
    this.snackBar.open(this.locale.translate(key), undefined, { duration: 4000 });
  }
}
