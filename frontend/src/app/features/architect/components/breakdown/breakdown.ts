import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { CompactPipe } from '@shared/format/compact.pipe';
import { formatPercent } from '@shared/format/format';
import { Note } from '@shared/note/note';
import { Term } from '@shared/term/term';
import { PARTS, type Counts, type Family, type Note as BreakdownNote, type PartRow } from '../../data/architect.types';

@Component({
  selector: 'app-breakdown',
  imports: [CompactPipe, Note, Term, TranslatePipe],
  templateUrl: './breakdown.html',
  styleUrl: './breakdown.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Breakdown {
  private readonly locale = inject(LocaleStore);

  readonly counts = input.required<Counts>();
  readonly family = input.required<Family>();
  readonly note = input.required<BreakdownNote | null>();

  readonly moe = computed(() => this.family() === 'moe_decoder');

  readonly rows = computed<readonly PartRow[]>(() => {
    const { parts, total } = this.counts();
    return PARTS.filter((spec) => parts[spec.key] > 0).map((spec) => ({
      key: spec.key,
      termKey: this.moe() && spec.moeTerm !== undefined ? spec.moeTerm : spec.key,
      tone: spec.tone,
      value: parts[spec.key],
      ratio: total > 0 ? parts[spec.key] / total : 0,
    }));
  });

  readonly summary = computed(() => {
    const parts = this.rows().map(
      (row) => `${this.locale.translate(`glossary.${row.termKey}.term`)}: ${this.percent(row.ratio)}`,
    );
    return `${this.locale.translate('architect.breakdown.where')}. ${parts.join(', ')}`;
  });

  readonly vocabularyShare = computed(() => this.percent(this.counts().embeddings_share));

  percent(ratio: number): string {
    return formatPercent(ratio, this.locale.locale());
  }
}
