import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButton } from '@angular/material/button';
import type { ErrorStateMatcher } from '@angular/material/core';
import {
  MAT_DIALOG_DATA,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogRef,
  MatDialogTitle,
} from '@angular/material/dialog';
import { MatError, MatFormField, MatHint, MatLabel } from '@angular/material/form-field';
import { MatIcon } from '@angular/material/icon';
import { MatInput } from '@angular/material/input';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSlideToggle } from '@angular/material/slide-toggle';

import type { ApiError } from '@core/http/api.types';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { Note } from '@shared/note/note';
import {
  ADDRESS_PATTERN,
  CONNECTABLE_KINDS,
  EXAMPLE_ADDRESS,
  KINDS_WITH_MODEL_NAME,
  NAME_MAX,
  type ConnectableKind,
  type Engine,
  type EngineChange,
  type EngineFormData,
  type NewEngine,
} from '../../data/serving.types';
import { ServingStore } from '../../state/serving.store';

@Component({
  selector: 'app-engine-form',
  imports: [
    FormsModule,
    MatButton,
    MatDialogActions,
    MatDialogClose,
    MatDialogContent,
    MatDialogTitle,
    MatError,
    MatFormField,
    MatHint,
    MatIcon,
    MatInput,
    MatLabel,
    MatOption,
    MatSelect,
    MatSlideToggle,
    Note,
    TranslatePipe,
  ],
  templateUrl: './engine-form.html',
  styleUrl: './engine-form.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EngineFormDialog {
  private readonly store = inject(ServingStore);
  private readonly reference = inject<MatDialogRef<EngineFormDialog, boolean>>(MatDialogRef);

  readonly engine: Engine | null = inject<EngineFormData>(MAT_DIALOG_DATA).engine;
  readonly editing = this.engine !== null;

  readonly kinds = CONNECTABLE_KINDS;
  readonly nameMax = NAME_MAX;
  readonly exampleAddress = EXAMPLE_ADDRESS;

  readonly name = signal(this.engine?.name ?? '');
  readonly kind = signal<ConnectableKind>(
    CONNECTABLE_KINDS.find((kind) => kind === this.engine?.kind) ?? CONNECTABLE_KINDS[0],
  );
  readonly address = signal(this.engine?.base_url ?? '');
  readonly modelName = signal(this.engine?.model_name ?? '');
  readonly apiKey = signal('');
  readonly removeKey = signal(false);
  readonly makeDefault = signal(this.engine?.is_default ?? false);
  readonly submitted = signal(false);
  readonly failure = signal<ApiError | null>(null);

  readonly busy = this.store.saving;

  readonly usesModelName = computed(() => KINDS_WITH_MODEL_NAME.includes(this.kind()));
  readonly defaultLocked = this.engine?.is_default === true;
  readonly keySaved = this.engine?.has_api_key === true;

  readonly nameInvalid = computed(() => this.submitted() && this.name().trim() === '');
  readonly addressInvalid = computed(() => this.submitted() && !ADDRESS_PATTERN.test(this.address().trim()));
  readonly nameErrors: ErrorStateMatcher = { isErrorState: () => this.nameInvalid() };
  readonly addressErrors: ErrorStateMatcher = { isErrorState: () => this.addressInvalid() };

  async submit(): Promise<void> {
    this.submitted.set(true);
    if (this.nameInvalid() || this.addressInvalid()) {
      return;
    }
    if (this.engine === null) {
      this.finish(await this.store.connect(this.newEngine()));
      return;
    }
    const change = this.changes(this.engine);
    if (Object.keys(change).length === 0) {
      this.reference.close(false);
      return;
    }
    this.finish(await this.store.save(this.engine, change));
  }

  private finish(failure: ApiError | null): void {
    this.failure.set(failure);
    if (failure === null) {
      this.reference.close(true);
    }
  }

  private newEngine(): NewEngine {
    const modelName = this.modelName().trim();
    const apiKey = this.apiKey().trim();
    return {
      name: this.name().trim(),
      kind: this.kind(),
      base_url: this.address().trim(),
      is_default: this.makeDefault(),
      ...(this.usesModelName() && modelName !== '' ? { model_name: modelName } : {}),
      ...(apiKey !== '' ? { api_key: apiKey } : {}),
    };
  }

  private changes(engine: Engine): EngineChange {
    const name = this.name().trim();
    const address = this.address().trim().replace(/\/+$/, '');
    const modelName = this.usesModelName() ? this.modelName().trim() : engine.model_name;
    const apiKey = this.apiKey().trim();
    return {
      ...(name !== engine.name ? { name } : {}),
      ...(address !== engine.base_url ? { base_url: address } : {}),
      ...(modelName !== engine.model_name ? { model_name: modelName } : {}),
      ...(this.removeKey() ? { api_key: '' } : {}),
      ...(!this.removeKey() && apiKey !== '' ? { api_key: apiKey } : {}),
      ...(this.makeDefault() && !engine.is_default ? { is_default: true } : {}),
    };
  }
}
