import { BreakpointObserver } from '@angular/cdk/layout';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { MatButton, MatIconButton } from '@angular/material/button';
import { MatIcon } from '@angular/material/icon';
import { MatListItem, MatListItemIcon, MatListItemTitle, MatNavList } from '@angular/material/list';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatSidenav, MatSidenavContainer, MatSidenavContent } from '@angular/material/sidenav';
import { MatToolbar } from '@angular/material/toolbar';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { map } from 'rxjs';

import { rolesFrom } from '@core/auth/roles';
import { AuthStore } from '@core/auth/state/auth.store';
import { LocaleSwitcher } from '@core/i18n/locale-switcher/locale-switcher';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { UiModeSwitcher } from '@core/ui/ui-mode-switcher/ui-mode-switcher';
import { NAVIGATION } from './navigation';

// Mirrors $screen-lg in src/styles/_layout.scss: a media query in code cannot read the Sass variable.
const WIDE = '(min-width: 64rem)';

@Component({
  selector: 'app-shell',
  imports: [
    LocaleSwitcher,
    MatButton,
    MatIcon,
    MatIconButton,
    MatListItem,
    MatListItemIcon,
    MatListItemTitle,
    MatMenu,
    MatMenuItem,
    MatMenuTrigger,
    MatNavList,
    MatSidenav,
    MatSidenavContainer,
    MatSidenavContent,
    MatToolbar,
    RouterLink,
    RouterLinkActive,
    RouterOutlet,
    TranslatePipe,
    UiModeSwitcher,
  ],
  templateUrl: './shell.html',
  styleUrl: './shell.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Shell {
  private readonly auth = inject(AuthStore);

  readonly wide = toSignal(
    inject(BreakpointObserver)
      .observe(WIDE)
      .pipe(map((state) => state.matches)),
    { initialValue: false },
  );

  readonly menuOpen = signal(false);

  readonly opened = computed(() => this.wide() || this.menuOpen());

  readonly items = computed(() => NAVIGATION.filter((item) => this.auth.hasAnyGroup(rolesFrom(item.role))));

  readonly displayName = this.auth.displayName;

  openMenu(): void {
    this.menuOpen.set(true);
  }

  closeMenu(): void {
    this.menuOpen.set(false);
  }

  async signOut(): Promise<void> {
    await this.auth.signOut();
  }
}
