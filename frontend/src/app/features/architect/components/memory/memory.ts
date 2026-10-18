import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { MatIcon } from '@angular/material/icon';

import { TranslatePipe } from '@core/i18n/translate.pipe';
import { BytesPipe } from '@shared/format/bytes.pipe';
import { Term } from '@shared/term/term';
import { FIT_ICONS, type Memory, type MemoryOption } from '../../data/architect.types';

@Component({
  selector: 'app-training-memory',
  imports: [BytesPipe, MatIcon, Term, TranslatePipe],
  templateUrl: './memory.html',
  styleUrl: './memory.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TrainingMemory {
  readonly memory = input.required<Memory>();

  readonly icons = FIT_ICONS;

  readonly options = computed<readonly MemoryOption[]>(() => {
    const memory = this.memory();
    return [
      {
        key: 'adamw',
        optimizer: memory.adamw_bytes,
        activations: memory.activation_bytes,
        runtime: memory.training_bytes - memory.adamw_bytes - memory.activation_bytes,
        total: memory.training_bytes,
        fit: memory.fit,
      },
      {
        key: 'adamw8',
        optimizer: memory.adamw_8bit_bytes,
        activations: memory.activation_bytes,
        runtime: memory.training_8bit_bytes - memory.adamw_8bit_bytes - memory.activation_bytes,
        total: memory.training_8bit_bytes,
        fit: memory.fit_8bit,
      },
    ];
  });

  readonly cpuOnly = computed(() => this.memory().fit.verdict === 'cpu_only');
}
