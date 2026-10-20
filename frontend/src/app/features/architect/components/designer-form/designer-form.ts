import { BreakpointObserver } from '@angular/cdk/layout';
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { MatButtonToggle, MatButtonToggleGroup } from '@angular/material/button-toggle';
import type { ErrorStateMatcher } from '@angular/material/core';
import { MatError, MatFormField, MatHint, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatSlideToggle } from '@angular/material/slide-toggle';
import { map } from 'rxjs';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { formatNumber } from '@shared/format/format';
import { Note } from '@shared/note/note';
import { Term } from '@shared/term/term';
import {
  FAMILIES,
  FAMILY_TERMS,
  FIELDS,
  GROUPS,
  LIMITS,
  TOKENIZER_EXAMPLE,
  TOKENIZER_MAX,
  type FieldSpec,
  type Family,
  type NumberKey,
  type ViewGroup,
} from '../../data/architect.types';
import { ArchitectStore } from '../../state/architect.store';

// Mirrors $screen-sm in src/styles/_layout.scss: a media query in code cannot read the Sass variable.
const ROOMY = '(min-width: 36rem)';

@Component({
  selector: 'app-designer-form',
  imports: [
    FormsModule,
    MatButtonToggle,
    MatButtonToggleGroup,
    MatError,
    MatFormField,
    MatHint,
    MatInput,
    MatLabel,
    MatSlideToggle,
    Note,
    Term,
    TranslatePipe,
  ],
  templateUrl: './designer-form.html',
  styleUrl: './designer-form.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DesignerForm {
  private readonly store = inject(ArchitectStore);
  private readonly locale = inject(LocaleStore);
  private readonly matchers = new Map<NumberKey, ErrorStateMatcher>();

  readonly families = FAMILIES;
  readonly tokenizerExample = TOKENIZER_EXAMPLE;
  readonly tokenizerMax = TOKENIZER_MAX;

  readonly blueprint = this.store.blueprint;
  readonly family = this.store.family;
  readonly errors = this.store.fieldErrors;
  readonly vocabularyNote = this.store.vocabularyNote;

  readonly roomy = toSignal(
    inject(BreakpointObserver)
      .observe(ROOMY)
      .pipe(map((state) => state.matches)),
    { initialValue: true },
  );

  readonly familyTerm = computed(() => FAMILY_TERMS[this.family()]);
  readonly moe = computed(() => this.family() === 'moe_decoder');
  readonly decoder = computed(() => this.family() !== 'encoder_decoder');

  readonly groups = computed<readonly ViewGroup[]>(() => {
    const family = this.family();
    return GROUPS.map((group) => ({
      ...group,
      fields: FIELDS.filter((field) => field.group === group.key && field.families.includes(family)),
    }));
  });

  wording(spec: FieldSpec | ViewGroup): string {
    return this.moe() && spec.moeWording ? 'Moe' : '';
  }

  range(key: NumberKey): string {
    const { min, max } = LIMITS[key];
    const language = this.locale.locale();
    return this.locale.translate('architect.field.range', {
      min: formatNumber(min, language),
      max: formatNumber(max, language),
    });
  }

  matcher(key: NumberKey): ErrorStateMatcher {
    let found = this.matchers.get(key);
    if (found === undefined) {
      found = { isErrorState: () => this.errors()[key] !== undefined };
      this.matchers.set(key, found);
    }
    return found;
  }

  chooseFamily(family: Family): void {
    this.store.setFamily(family);
  }

  setNumber(key: NumberKey, value: number | null): void {
    this.store.setNumber(key, value);
  }

  setTokenizer(value: string): void {
    this.store.setTokenizer(value);
  }

  setTied(tied: boolean): void {
    this.store.setTied(tied);
  }
}
