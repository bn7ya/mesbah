import { ChangeDetectionStrategy, Component, computed, inject, input, model } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatOption, type ErrorStateMatcher } from '@angular/material/core';
import { MatError, MatFormField, MatHint, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatSelect } from '@angular/material/select';
import { MatSlideToggle } from '@angular/material/slide-toggle';

import { LocaleStore } from '@core/i18n/locale.store';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { formatSignificant } from '@shared/format/format';
import { Term } from '@shared/term/term';
import {
  EXACT_FIELDS,
  EXPERT_FIELDS,
  EXPERT_SWITCHES,
  RANK_CHOICES,
  type FieldProblem,
  type Hyperparams,
  type LoraRank,
  type NumberField,
  type SettingKey,
  type SwitchField,
} from '../../data/training.types';
import { problemsOf } from '../../state/train-settings';

@Component({
  selector: 'app-expert-settings',
  imports: [
    FormsModule,
    MatError,
    MatFormField,
    MatHint,
    MatInput,
    MatLabel,
    MatOption,
    MatSelect,
    MatSlideToggle,
    Term,
    TranslatePipe,
  ],
  templateUrl: './expert-settings.html',
  styleUrl: './expert-settings.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ExpertSettings {
  private readonly locale = inject(LocaleStore);
  private readonly matchers = new Map<SettingKey, ErrorStateMatcher>();

  readonly settings = model.required<Hyperparams>();
  readonly defaults = input.required<Hyperparams>();
  readonly disabled = input(false);

  readonly exactFields = EXACT_FIELDS;
  readonly expertFields = EXPERT_FIELDS;
  readonly switches = EXPERT_SWITCHES;
  readonly rankChoices = RANK_CHOICES;
  readonly terms: readonly string[] = [
    ...new Set([...EXACT_FIELDS, ...EXPERT_FIELDS].flatMap((field) => (field.termKey === null ? [] : [field.termKey])).concat('rank')),
  ];

  readonly problems = computed(() => problemsOf(this.settings()));

  matcher(key: SettingKey): ErrorStateMatcher {
    let matcher = this.matchers.get(key);
    if (matcher === undefined) {
      matcher = { isErrorState: () => this.problem(key) !== undefined };
      this.matchers.set(key, matcher);
    }
    return matcher;
  }

  problem(key: SettingKey): FieldProblem | undefined {
    return this.problems().find((problem) => problem.key === key);
  }

  value(key: SettingKey): number | null {
    return this.settings()[key] as number | null;
  }

  plain(value: number): string {
    return formatSignificant(value, this.locale.locale(), 6);
  }

  defaultOf(field: NumberField): string {
    const value = this.defaults()[field.key] as number | null;
    return value === null ? this.locale.translate('training.expert.noLimit') : this.plain(value);
  }

  flag(field: SwitchField): boolean {
    return this.settings()[field.key] as boolean;
  }

  setNumber(key: SettingKey, value: number | null): void {
    this.settings.update((current) => ({ ...current, [key]: value }));
  }

  setFlag(key: SettingKey, checked: boolean): void {
    this.settings.update((current) => ({ ...current, [key]: checked }));
  }

  setRank(rank: LoraRank): void {
    this.settings.update((current) => ({ ...current, lora_rank: rank }));
  }
}
