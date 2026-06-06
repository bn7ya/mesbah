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
  styleUrl: './app.scss',
})
export class App implements OnInit {
  private api = inject(Api);
  readonly sys = signal<SystemInfo | null>(null);
  readonly theme = signal<Theme>('dark');

  ngOnInit(): void {
    // Saved choice wins; otherwise default to dark (easy on the eyes).
    const saved = localStorage.getItem(THEME_KEY) as Theme | null;
    this.applyTheme(saved ?? 'dark');
    this.poll();
    setInterval(() => this.poll(), 5000);
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
    this.api.system().subscribe({ next: (s) => this.sys.set(s), error: () => {} });
  }

  vramPct(): number {
    const e = this.sys()?.engine;
    if (!e?.vram_total_gb || e.vram_used_gb == null) return 0;
    return Math.round((e.vram_used_gb / e.vram_total_gb) * 100);
  }
}
