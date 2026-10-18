import { ChangeDetectionStrategy, Component, Injector, computed, inject, input } from '@angular/core';
import { MatIconButton } from '@angular/material/button';
import { MatCard } from '@angular/material/card';
import { MatChip, MatChipAvatar, MatChipSet } from '@angular/material/chips';
import { MatDialog } from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatMenu, MatMenuItem, MatMenuTrigger } from '@angular/material/menu';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTooltip } from '@angular/material/tooltip';
import { firstValueFrom } from 'rxjs';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { UiModeStore } from '@core/ui/ui-mode.store';
import { confirmAction } from '@shared/confirm-dialog/confirm-dialog';
import { BytesPipe } from '@shared/format/bytes.pipe';
import { CompactPipe } from '@shared/format/compact.pipe';
import { DateTimePipe } from '@shared/format/datetime.pipe';
import { formatNumber, formatPercent, formatSignificant } from '@shared/format/format';
import { Term } from '@shared/term/term';
import { VersionNamePipe, versionName } from '@shared/version/version-name.pipe';
import { SLIVER, type RenameDialogData, type SizeShare, type Version } from '../../data/versions.types';
import { RenameVersionDialog } from '../../dialogs/rename-version/rename-version';
import { VersionsStore } from '../../state/versions.store';

@Component({
  selector: 'app-version-row',
  imports: [
    BytesPipe,
    CompactPipe,
    DateTimePipe,
    MatCard,
    MatChip,
    MatChipAvatar,
    MatChipSet,
    MatIcon,
    MatIconButton,
    MatMenu,
    MatMenuItem,
    MatMenuTrigger,
    MatProgressBar,
    MatTooltip,
    Term,
    TranslatePipe,
    VersionNamePipe,
  ],
  templateUrl: './version-row.html',
  styleUrl: './version-row.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VersionRow {
  private readonly store = inject(VersionsStore);
  private readonly ui = inject(UiModeStore);
  private readonly dialog = inject(MatDialog);
  private readonly injector = inject(Injector);
  private readonly snackBar = inject(MatSnackBar);
  private readonly locale = inject(LocaleStore);

  readonly version = input.required<Version>();

  readonly canWrite = this.store.canWrite;
  readonly expert = this.ui.expert;

  readonly busy = computed(() => this.store.working().includes(this.version().id));
  readonly label = computed(() => `v${this.version().number} · ${versionName(this.version(), this.locale)}`);

  readonly share = computed<SizeShare | null>(() => {
    const { size_bytes, full_size_bytes } = this.version();
    if (full_size_bytes <= 0) {
      return null;
    }
    const ratio = Math.min(1, size_bytes / full_size_bytes);
    const sliver = ratio < SLIVER;
    return {
      ratio,
      key: sliver ? 'versions.size.sliver' : 'versions.size.change',
      percent: formatPercent(sliver ? SLIVER : ratio, this.locale.locale()),
    };
  });

  readonly hasExpertDetails = computed(() => {
    const { kind, lora_rank, delta } = this.version();
    return kind === 'lora' || lora_rank !== null || delta !== null;
  });

  readonly removeBlocker = computed<string | null>(() => {
    const version = this.version();
    if (version.parent_id === null) {
      return 'errors.root_version_kept';
    }
    return version.is_active ? 'errors.active_version_kept' : null;
  });

  readonly activateHint = computed(() =>
    this.version().is_active ? 'versions.menu.alreadyActive' : 'versions.menu.activateHint',
  );

  count(value: number): string {
    return formatNumber(value, this.locale.locale());
  }

  significant(value: number): string {
    return formatSignificant(value, this.locale.locale());
  }

  async makeActive(): Promise<void> {
    if (await this.store.activate(this.version())) {
      this.report('versions.activated', { name: this.label() });
    }
  }

  async rename(): Promise<void> {
    const reference = this.dialog.open<RenameVersionDialog, RenameDialogData, boolean>(RenameVersionDialog, {
      injector: this.injector,
      data: { version: this.version() },
      width: '35rem',
      maxWidth: '95vw',
      autoFocus: 'first-tabbable',
    });
    if (await firstValueFrom(reference.afterClosed())) {
      this.report('versions.renamed');
    }
  }

  async remove(): Promise<void> {
    const confirmed = await confirmAction(this.dialog, {
      titleKey: 'versions.remove.title',
      bodyKey: 'versions.remove.body',
      confirmKey: 'versions.remove.confirm',
      values: { name: this.label() },
      destructive: true,
    });
    if (confirmed && (await this.store.remove(this.version()))) {
      this.report('versions.removed');
    }
  }

  private report(key: string, values?: Readonly<Record<string, string>>): void {
    this.snackBar.open(this.locale.translate(key, values), undefined, { duration: 4000 });
  }
}
