import { ChangeDetectionStrategy, Component, Injector, computed, inject } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatCard } from '@angular/material/card';
import { MatDialog } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatPaginator, type PageEvent } from '@angular/material/paginator';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyState } from '@shared/empty-state/empty-state';
import { CompactPipe } from '@shared/format/compact.pipe';
import { DateTimePipe } from '@shared/format/datetime.pipe';
import { Note } from '@shared/note/note';
import { VersionNamePipe } from '@shared/version/version-name.pipe';
import { NewProjectDialog } from '../../dialogs/new-project/new-project';
import { ProjectsStore } from '../../state/projects.store';

@Component({
  selector: 'app-projects-page',
  imports: [
    CompactPipe,
    DateTimePipe,
    EmptyState,
    MatButton,
    MatCard,
    MatIcon,
    MatPaginator,
    MatProgressBar,
    Note,
    RouterLink,
    TranslatePipe,
    VersionNamePipe,
  ],
  templateUrl: './projects.html',
  styleUrl: './projects.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProjectsPage {
  private readonly store = inject(ProjectsStore);
  private readonly dialog = inject(MatDialog);
  private readonly injector = inject(Injector);
  private readonly router = inject(Router);
  private readonly snackBar = inject(MatSnackBar);
  private readonly locale = inject(LocaleStore);

  readonly page = this.store.page;
  readonly pageIndex = this.store.pageIndex;
  readonly pageSize = this.store.pageSize;
  readonly loading = this.store.loading;
  readonly error = this.store.error;
  readonly canWrite = this.store.canWrite;

  readonly empty = computed(() => this.page().results.length === 0 && !this.loading() && this.error() === null);
  readonly paged = computed(() => this.page().count > this.pageSize());

  readonly emptyMode = computed<'read' | 'start' | 'download'>(() => {
    if (!this.canWrite()) {
      return 'read';
    }
    const noModel = this.store.readyModels().length === 0 && !this.store.modelsLoading();
    return noModel ? 'download' : 'start';
  });

  constructor() {
    void this.store.visit();
  }

  tryAgain(): void {
    void this.store.load();
  }

  turnPage(event: PageEvent): void {
    void this.store.load(event.pageIndex, event.pageSize);
  }

  async newProject(): Promise<void> {
    const reference = this.dialog.open<NewProjectDialog, undefined, string>(NewProjectDialog, {
      injector: this.injector,
      width: '38rem',
      maxWidth: '95vw',
      autoFocus: 'first-tabbable',
    });
    const id = await firstValueFrom(reference.afterClosed());
    if (id) {
      this.snackBar.open(this.locale.translate('projects.created'), undefined, { duration: 4000 });
      await this.router.navigate(['/projects', id]);
    }
  }
}
