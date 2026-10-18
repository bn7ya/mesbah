import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject } from '@angular/core';
import { MatButton } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogTitle,
} from '@angular/material/dialog';
import { MatIcon } from '@angular/material/icon';
import { MatProgressBar } from '@angular/material/progress-bar';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { UiModeStore } from '@core/ui/ui-mode.store';
import { CompactPipe } from '@shared/format/compact.pipe';
import { formatNumber, formatSignificant } from '@shared/format/format';
import { Term } from '@shared/term/term';
import { ChangeMapView } from '../../components/change-map/change-map';
import { MAX_TINT, type VersionDialogData, type VersionKind } from '../../data/versions.types';
import { VersionsStore } from '../../state/versions.store';
import { versionLabel } from '../../state/version-label';

const NO_MAP: Readonly<Record<VersionKind, string>> = {
  base: 'versions.changes.base',
  scratch_root: 'versions.changes.scratch',
  lora: 'versions.changes.missing',
};

@Component({
  selector: 'app-version-changes',
  imports: [
    ChangeMapView,
    CompactPipe,
    MatButton,
    MatDialogActions,
    MatDialogClose,
    MatDialogContent,
    MatDialogTitle,
    MatIcon,
    MatProgressBar,
    Term,
    TranslatePipe,
  ],
  templateUrl: './version-changes.html',
  styleUrl: './version-changes.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VersionChangesDialog {
  private readonly store = inject(VersionsStore);
  private readonly locale = inject(LocaleStore);
  private readonly ui = inject(UiModeStore);

  readonly data = inject<VersionDialogData>(MAT_DIALOG_DATA);
  readonly label = versionLabel(this.data.version, this.locale);

  readonly changes = this.store.versionChanges;
  readonly map = this.store.changeMap;
  readonly loading = this.store.changesLoading;
  readonly loadFailure = this.store.changesLoadError;
  readonly expert = this.ui.expert;

  readonly legend: readonly number[] = [0, 0.25, 0.5, 0.75, 1].map((share) => share * MAX_TINT);

  readonly note = computed<string | null>(() => {
    const map = this.map();
    return map !== null && map.rows.length === 0 ? NO_MAP[this.data.version.kind] : null;
  });

  readonly topLayers = computed<string>(() => {
    const layers = this.map()?.topLayers ?? [];
    const numbers = layers.map((layer) => formatNumber(layer, this.locale.locale()));
    return new Intl.ListFormat(this.locale.locale(), { type: 'conjunction' }).format(numbers);
  });

  constructor() {
    this.store.showChanges(this.data.version.id);
    inject(DestroyRef).onDestroy(() => this.store.forgetChanges());
  }

  significant(value: number): string {
    return formatSignificant(value, this.locale.locale());
  }

  count(value: number): string {
    return formatNumber(value, this.locale.locale());
  }

  tryAgain(): void {
    this.store.reloadChanges();
  }
}
