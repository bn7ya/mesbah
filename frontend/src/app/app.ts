import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterOutlet, RouterLink } from '@angular/router';
import { DecimalPipe } from '@angular/common';
import { ToastModule } from 'primeng/toast';
import { ConfirmDialogModule } from 'primeng/confirmdialog';
import { Api } from './core/api';
import { SystemInfo } from './core/types';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, DecimalPipe, ToastModule, ConfirmDialogModule],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App implements OnInit {
  private api = inject(Api);
  readonly sys = signal<SystemInfo | null>(null);

  ngOnInit(): void {
    // Permanent dark surface (glass tokens assume dark).
    document.documentElement.classList.add('dark');
    this.poll();
    setInterval(() => this.poll(), 5000);
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
