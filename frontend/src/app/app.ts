import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterOutlet, RouterLink } from '@angular/router';
import { DecimalPipe } from '@angular/common';
import { ToastModule } from 'primeng/toast';
import { ConfirmDialogModule } from 'primeng/confirmdialog';
import { Api } from './core/api';
import { SystemInfo } from './core/types';

type Theme = 'light' | 'dark';
const THEME_KEY = 'misbah-theme';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, DecimalPipe, ToastModule, ConfirmDialogModule],
  templateUrl: './app.html',
})
export class App implements OnInit {
  private api = inject(Api);
  readonly sys = signal<SystemInfo | null>(null);
  readonly theme = signal<Theme>('light');
  // First-run GPU onboarding — shown once until the user picks a GPU.
  readonly showOnboarding = signal(false);
  private onboardChecked = false;

  ngOnInit(): void {
    // Saved choice wins; otherwise default to a clean light theme (Notion-like).
    const saved = localStorage.getItem(THEME_KEY) as Theme | null;
    this.applyTheme(saved ?? 'light');
    this.poll();
    setInterval(() => this.poll(), 5000);
  }

  /** Record the first-run GPU choice (or null for CPU-only), then dismiss. */
  onboard(index: number | null): void {
    this.api.onboard(index).subscribe({
      next: () => { this.showOnboarding.set(false); this.poll(); },
      error: () => {},
    });
  }

  toggleTheme(): void {
    this.applyTheme(this.theme() === 'dark' ? 'light' : 'dark');
  }

  private applyTheme(t: Theme): void {
    this.theme.set(t);
    document.documentElement.classList.toggle('dark', t === 'dark');
    localStorage.setItem(THEME_KEY, t);
  }

  private poll(): void {
    this.api.system().subscribe({
      next: (s) => {
        this.sys.set(s);
        // Show the GPU picker once on first run (until the user is onboarded).
        if (!this.onboardChecked) {
          this.onboardChecked = true;
          this.showOnboarding.set(!s.onboarded);
        }
      },
      error: () => {},
    });
  }

  /** Short hardware label for the status chip: the real GPU name, else CPU-only. */
  gpuLabel(s: SystemInfo): string {
    if (s.selected_gpu?.name) return s.selected_gpu.name.replace(/^NVIDIA\s+/i, '');
    return s.engine.runtime_available ? 'GPU runtime' : 'CPU only';
  }

  vramPct(): number {
    const e = this.sys()?.engine;
    if (!e?.vram_total_gb || e.vram_used_gb == null) return 0;
    return Math.round((e.vram_used_gb / e.vram_total_gb) * 100);
  }
}
