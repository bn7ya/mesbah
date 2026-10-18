import { ChangeDetectionStrategy, Component, computed, effect, inject, input, untracked } from '@angular/core';
import { MatButton } from '@angular/material/button';
import { MatChip, MatChipAvatar, MatChipSet } from '@angular/material/chips';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatTabLink, MatTabNav, MatTabNavPanel } from '@angular/material/tabs';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { rolesFrom } from '@core/auth/roles';
import { AuthStore } from '@core/auth/state/auth.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { CompactPipe } from '@shared/format/compact.pipe';
import { VersionNamePipe } from '@shared/version/version-name.pipe';
import { PROJECT_TABS } from '../../project-tabs';
import { ProjectStore } from '../../state/project.store';

@Component({
  selector: 'app-project-frame',
  imports: [
    CompactPipe,
    MatButton,
    MatChip,
    MatChipAvatar,
    MatChipSet,
    MatIcon,
    MatProgressBar,
    MatTabLink,
    MatTabNav,
    MatTabNavPanel,
    RouterLink,
    RouterLinkActive,
    RouterOutlet,
    TranslatePipe,
    VersionNamePipe,
  ],
  templateUrl: './project-frame.html',
  styleUrl: './project-frame.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProjectFrame {
  private readonly store = inject(ProjectStore);
  private readonly auth = inject(AuthStore);

  readonly projectId = input.required<string>();

  readonly project = this.store.project;
  readonly loading = this.store.loading;
  readonly error = this.store.error;
  readonly activeVersion = this.store.activeVersion;

  readonly tabs = computed(() => PROJECT_TABS.filter((tab) => this.auth.hasAnyGroup(rolesFrom(tab.role))));

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
