import { Injectable, computed, inject, signal } from '@angular/core';
import { Api } from './api';

export type UiMode = 'simple' | 'expert';

/**
 * App-wide Simple/Expert mode. Simple (the default) hides advanced/technical
 * controls (from-scratch training, raw hyperparameters, prompt editors, Data
 * Lab/Versions/Auto-Enhance) so a non-technical user only ever sees the
 * golden path: pick a model → chat & correct → train. Expert reveals every
 * control exactly as it works today. Persisted via `AppSettings.ui_mode`
 * (`features/settings`), same pattern as `theme`.
 */
@Injectable({ providedIn: 'root' })
export class UiModeService {
  private api = inject(Api);
  private readonly _mode = signal<UiMode>('simple');
  private loaded = false;

  readonly mode = this._mode.asReadonly();
  readonly isSimple = computed(() => this._mode() === 'simple');

  /** Fetch the persisted mode once. Safe to call from every component that
   * needs it — only the first call hits the network. */
  load(): void {
    if (this.loaded) return;
    this.loaded = true;
    this.api.getSettings().subscribe({
      next: (s) => this._mode.set(s.ui_mode === 'expert' ? 'expert' : 'simple'),
      error: () => {},
    });
  }

  set(mode: UiMode): void {
    this._mode.set(mode);   // optimistic — the toggle should feel instant
    this.api.updateSettings({ ui_mode: mode }).subscribe({ error: () => {} });
  }

  toggle(): void { this.set(this.isSimple() ? 'expert' : 'simple'); }
}
