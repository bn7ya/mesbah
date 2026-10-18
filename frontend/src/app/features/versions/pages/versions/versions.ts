import { ChangeDetectionStrategy, Component, computed, effect, inject, input, untracked } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';

import { TranslatePipe } from '@core/i18n/translate.pipe';
import { Term } from '@shared/term/term';
import { VersionBranch } from '../../components/version-branch/version-branch';
import { VersionsStore } from '../../state/versions.store';

@Component({
  selector: 'app-versions-page',
  imports: [MatButton, MatIcon, MatProgressBar, Term, TranslatePipe, VersionBranch],
  templateUrl: './versions.html',
  styleUrl: './versions.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VersionsPage {
  private readonly store = inject(VersionsStore);

  readonly projectId = input.required<string>();

  readonly tree = this.store.tree;
  readonly loading = this.store.loading;
  readonly loadError = this.store.loadError;
  readonly error = this.store.error;

  readonly onlyBase = computed(() => this.store.versions().length === 1);

  constructor() {
    effect(() => {
      const id = this.projectId();
      untracked(() => this.store.open(id));
    });
  }

  tryAgain(): void {
    this.store.reload();
  }
}
