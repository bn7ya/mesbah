import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { BytesPipe } from '../format/bytes.pipe';
import { formatBytes } from '../format/format';
import type { MeterSegment, MeterSlice } from './meter.types';

@Component({
  selector: 'app-meter',
  imports: [BytesPipe, TranslatePipe],
  templateUrl: './meter.html',
  styleUrl: './meter.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Meter {
  private readonly locale = inject(LocaleStore);

  readonly label = input.required<string>();
  readonly totalBytes = input.required<number>();
  readonly segments = input.required<readonly MeterSegment[]>();

  readonly slices = computed<readonly MeterSlice[]>(() => {
    const total = Math.max(this.totalBytes(), 1);
    return this.segments().map((segment) => ({
      ...segment,
      share: Math.min(100, (Math.max(segment.bytes, 0) / total) * 100),
    }));
  });

  readonly freeBytes = computed(() =>
    Math.max(0, this.totalBytes() - this.segments().reduce((sum, segment) => sum + segment.bytes, 0)),
  );

  readonly summary = computed(() => {
    const locale = this.locale.locale();
    const parts = this.segments().map((segment) => `${segment.label}: ${formatBytes(segment.bytes, locale)}`);
    parts.push(`${this.locale.translate('meter.free')}: ${formatBytes(this.freeBytes(), locale)}`);
    return `${this.label()}. ${parts.join(', ')}`;
  });
}
