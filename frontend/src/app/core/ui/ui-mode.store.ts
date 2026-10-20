import { Injectable, computed, effect, signal } from '@angular/core';

import { UI_MODES, type UiMode } from './ui-mode.types';

const STORAGE_KEY = 'ui-mode';

@Injectable({ providedIn: 'root' })
export class UiModeStore {
  readonly mode = signal<UiMode>(readInitialMode());

  readonly expert = computed(() => this.mode() === 'expert');

  constructor() {
    effect(() => {
      localStorage.setItem(STORAGE_KEY, this.mode());
    });
  }

  setMode(mode: UiMode): void {
    this.mode.set(mode);
  }
}

function readInitialMode(): UiMode {
  const stored = localStorage.getItem(STORAGE_KEY);
  return UI_MODES.find((mode) => mode === stored) ?? 'simple';
}
