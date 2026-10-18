import { ChangeDetectionStrategy, Component, Injector, inject } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
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

import { ROLE_LADDER, type Role } from '@core/auth/roles.types';
import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { confirmAction } from '@shared/confirm-dialog/confirm-dialog';
import type { Member } from '../../data/members.types';
import { AddMemberDialog } from '../../dialogs/add-member/add-member';
import { MembersStore } from '../../state/members.store';

@Component({
  selector: 'app-members-page',
  imports: [
    MatButton,
    MatCell,
    MatCellDef,
    MatColumnDef,
    MatHeaderCell,
    MatHeaderCellDef,
    MatHeaderRow,
    MatHeaderRowDef,
    MatIcon,
    MatMenu,
    MatMenuItem,
    MatMenuTrigger,
    MatPaginator,
    MatProgressBar,
    MatRow,
    MatRowDef,
    MatTable,
    TranslatePipe,
  ],
  templateUrl: './members.html',
  styleUrl: './members.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MembersPage {
  private readonly store = inject(MembersStore);
  private readonly dialog = inject(MatDialog);
  private readonly injector = inject(Injector);
  private readonly snackBar = inject(MatSnackBar);
  private readonly locale = inject(LocaleStore);

  readonly page = this.store.page;
  readonly pageIndex = this.store.pageIndex;
  readonly pageSize = this.store.pageSize;
  readonly loading = this.store.loading;
  readonly busy = this.store.busy;
  readonly error = this.store.error;

  readonly roles = ROLE_LADDER;
  readonly columns = ['person', 'role', 'status', 'actions'];

  constructor() {
    void this.store.load();
  }

  displayName(member: Member): string {
    return [member.first_name, member.last_name].filter(Boolean).join(' ');
  }

  turnPage(event: PageEvent): void {
    void this.store.load(event.pageIndex, event.pageSize);
  }

  async addMember(): Promise<void> {
    const reference = this.dialog.open<AddMemberDialog, undefined, boolean>(AddMemberDialog, {
      injector: this.injector,
      autoFocus: 'first-tabbable',
    });
    if (await firstValueFrom(reference.afterClosed())) {
      this.report('members.added');
    }
  }

  async setRole(member: Member, role: Role): Promise<void> {
    if (member.role === role) {
      return;
    }
    if (await this.store.change(member, { role })) {
      this.report('members.roleChanged');
    }
  }

  async setActive(member: Member, active: boolean): Promise<void> {
    if (!active) {
      const confirmed = await confirmAction(this.dialog, {
        titleKey: 'members.deactivate.title',
        bodyKey: 'members.deactivate.body',
        confirmKey: 'members.deactivate.confirm',
        values: { name: member.username },
        destructive: true,
      });
      if (!confirmed) {
        return;
      }
    }
    if (await this.store.change(member, { is_active: active })) {
      this.report(active ? 'members.reactivated' : 'members.deactivated');
    }
  }

  private report(key: string): void {
    this.snackBar.open(this.locale.translate(key), undefined, { duration: 4000 });
  }
}
