import { DOCUMENT } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';

import { TranslatePipe } from '@core/i18n/translate.pipe';
import { Term } from '@shared/term/term';
import { ServingStore } from '../../state/serving.store';
import { CodeBlock } from '../code-block/code-block';
import { guideFor } from './snippets';

@Component({
  selector: 'app-connect-guide',
  imports: [CodeBlock, Term, TranslatePipe],
  templateUrl: './connect-guide.html',
  styleUrl: './connect-guide.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConnectGuide {
  private readonly store = inject(ServingStore);
  private readonly origin = inject(DOCUMENT).location.origin;

  readonly slug = this.store.exampleSlug;
  readonly apis = computed(() => guideFor(this.origin, this.slug()));
}
