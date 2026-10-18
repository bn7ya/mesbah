import { ChangeDetectionStrategy, Component, inject, input } from '@angular/core';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { formatNumber, formatSignificant } from '@shared/format/format';
import type { ChangeCell, ChangeMap } from '../../data/versions.types';

@Component({
  selector: 'app-change-map',
  imports: [TranslatePipe],
  templateUrl: './change-map.html',
  styleUrl: './change-map.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ChangeMapView {
  private readonly locale = inject(LocaleStore);

  readonly map = input.required<ChangeMap>();

  layer(layer: number): string {
    return formatNumber(layer, this.locale.locale());
  }

  value(cell: ChangeCell): string {
    return cell.norm === null ? '–' : formatSignificant(cell.norm, this.locale.locale());
  }

  label(layer: number, cell: ChangeCell): string {
    return this.locale.translate(cell.norm === null ? 'versions.changes.cellNone' : 'versions.changes.cell', {
      layer: this.layer(layer),
      module: cell.module,
      value: this.value(cell),
    });
  }
}
