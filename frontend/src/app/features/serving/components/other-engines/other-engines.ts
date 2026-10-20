import { ChangeDetectionStrategy, Component, Injector, computed, inject } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatCard } from '@angular/material/card';
import { MatDialog } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatSnackBar } from '@angular/material/snack-bar';
import { firstValueFrom } from 'rxjs';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { confirmAction } from '@shared/confirm-dialog/confirm-dialog';
import { EmptyState } from '@shared/empty-state/empty-state';
import { Status } from '@shared/status/status';
import { Term } from '@shared/term/term';
import { KIND_TERMS, type Engine, type EngineFormData } from '../../data/serving.types';
import { EngineFormDialog } from '../../dialogs/engine-form/engine-form';
import { ServingStore } from '../../state/serving.store';
import { LoadedVersions } from '../loaded-versions/loaded-versions';

@Component({
  selector: 'app-other-engines',
  imports: [EmptyState, LoadedVersions, MatButton, MatCard, MatIcon, Status, Term, TranslatePipe],
  templateUrl: './other-engines.html',
  styleUrl: './other-engines.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class OtherEngines {
  private readonly store = inject(ServingStore);
  private readonly dialog = inject(MatDialog);
  private readonly injector = inject(Injector);
  private readonly snackBar = inject(MatSnackBar);
  private readonly locale = inject(LocaleStore);

  readonly engines = this.store.others;
  readonly canManage = this.store.canManage;

  readonly empty = computed(() => this.engines().length === 0);

  termOf(engine: Engine): string | null {
    return KIND_TERMS[engine.kind] ?? null;
  }

  isWorking(engine: Engine): boolean {
    return this.store.working().includes(engine.id);
  }

  async connect(): Promise<void> {
    if (await this.openForm(null)) {
      this.report('serving.others.connected');
    }
  }

  async edit(engine: Engine): Promise<void> {
    if (await this.openForm(engine)) {
      this.report('serving.others.saved');
    }
  }

  async toggle(engine: Engine): Promise<void> {
    if (await this.store.change(engine, { enabled: !engine.enabled })) {
      this.report(engine.enabled ? 'serving.others.turnedOff' : 'serving.others.turnedOn');
    }
  }

  async makeDefault(engine: Engine): Promise<void> {
    if (await this.store.change(engine, { is_default: true })) {
      this.report('serving.others.madeDefault');
    }
  }

  async disconnect(engine: Engine): Promise<void> {
    const confirmed = await confirmAction(this.dialog, {
      titleKey: 'serving.others.disconnectTitle',
      bodyKey: 'serving.others.disconnectBody',
      confirmKey: 'serving.others.disconnectConfirm',
      values: { name: engine.name },
      destructive: true,
    });
    if (confirmed && (await this.store.disconnect(engine))) {
      this.report('serving.others.disconnected');
    }
  }

  private async openForm(engine: Engine | null): Promise<boolean> {
    const reference = this.dialog.open<EngineFormDialog, EngineFormData, boolean>(EngineFormDialog, {
      injector: this.injector,
      data: { engine },
      width: '35rem',
      maxWidth: '95vw',
      autoFocus: 'first-tabbable',
    });
    return (await firstValueFrom(reference.afterClosed())) === true;
  }

  private report(key: string): void {
    this.snackBar.open(this.locale.translate(key), undefined, { duration: 4000 });
  }
}
