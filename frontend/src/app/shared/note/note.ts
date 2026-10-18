import { ChangeDetectionStrategy, Component, booleanAttribute, computed, input } from '@angular/core';
import { MatIcon } from '@angular/material/icon';

import type { NoteKind } from './note.types';

@Component({
  selector: 'app-note',
  imports: [MatIcon],
  templateUrl: './note.html',
  styleUrl: './note.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Note {
  readonly kind = input<NoteKind>('info');
  readonly icon = input<string | null>(null);
  readonly live = input(false, { transform: booleanAttribute });

  readonly glyph = computed(() => this.icon() ?? (this.kind() === 'error' ? 'fa-circle-exclamation' : 'fa-circle-info'));
  readonly role = computed(() => (this.kind() === 'error' ? 'alert' : this.live() ? 'status' : 'note'));
}
