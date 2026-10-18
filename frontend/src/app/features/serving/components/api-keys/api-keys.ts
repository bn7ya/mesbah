import { ChangeDetectionStrategy, Component, Injector, computed, inject } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatPaginator, type PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import {
  MatCell,
  MatCellDef,
  MatColumnDef,
  MatHeaderCell,
  MatHeaderCellDef,
  MatHeaderRow,
  MatHeaderRowDef,
  MatRow,
  MatRowDef,
  MatTable,
} from '@angular/material/table';
import { firstValueFrom } from 'rxjs';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { confirmAction } from '@shared/confirm-dialog/confirm-dialog';
import { EmptyState } from '@shared/empty-state/empty-state';
import { DateTimePipe } from '@shared/format/datetime.pipe';
import { Note } from '@shared/note/note';
import { Term } from '@shared/term/term';
import { KEYS_PAGE_SIZE_OPTIONS, type ApiKey } from '../../data/serving.types';
import { NewKeyDialog } from '../../dialogs/new-key/new-key';
import { ServingStore } from '../../state/serving.store';

@Component({
  selector: 'app-api-keys',
  imports: [
    DateTimePipe,
    EmptyState,
    MatButton,
    MatCell,
    MatCellDef,
    MatColumnDef,
    MatHeaderCell,
    MatHeaderCellDef,
    MatHeaderRow,
    MatHeaderRowDef,
    MatIcon,
    MatPaginator,
    MatProgressBar,
    MatRow,
    MatRowDef,
    MatTable,
    Note,
    Term,
    TranslatePipe,
  ],
  templateUrl: './api-keys.html',
  styleUrl: './api-keys.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ApiKeys {
  private readonly store = inject(ServingStore);
  private readonly dialog = inject(MatDialog);
  private readonly injector = inject(Injector);
  private readonly snackBar = inject(MatSnackBar);
  private readonly locale = inject(LocaleStore);

  readonly canTrain = this.store.canTrain;
  readonly page = this.store.keys;
  readonly pageIndex = this.store.keysPageIndex;
  readonly pageSize = this.store.keysPageSize;
  readonly loading = this.store.keysLoading;
  readonly error = this.store.keysError;

  readonly columns = ['name', 'prefix', 'owner', 'lastUsed', 'created', 'actions'];
  readonly pageSizeOptions = KEYS_PAGE_SIZE_OPTIONS;

  readonly empty = computed(() => this.page().count === 0 && !this.loading() && this.error() === null);

  isWorking(key: ApiKey): boolean {
    return this.store.keyWorking().includes(key.id);
  }

  turnPage(event: PageEvent): void {
    void this.store.loadKeys(event.pageIndex, event.pageSize);
  }

  async create(): Promise<void> {
    const reference = this.dialog.open<NewKeyDialog, undefined, boolean>(NewKeyDialog, {
      injector: this.injector,
      width: '35rem',
      maxWidth: '95vw',
      autoFocus: 'first-tabbable',
    });
    await firstValueFrom(reference.afterClosed());
  }

  async revoke(key: ApiKey): Promise<void> {
    const confirmed = await confirmAction(this.dialog, {
      titleKey: 'serving.keys.revokeTitle',
      bodyKey: 'serving.keys.revokeBody',
      confirmKey: 'serving.keys.revokeConfirm',
      values: { name: key.name },
      destructive: true,
    });
    if (confirmed && (await this.store.revokeKey(key))) {
      this.snackBar.open(this.locale.translate('serving.keys.revoked'), undefined, { duration: 4000 });
    }
  }
}
