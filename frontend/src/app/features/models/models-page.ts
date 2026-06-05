import { Component, OnInit, inject, signal } from '@angular/core';
import { DecimalPipe, NgTemplateOutlet } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { TagModule } from 'primeng/tag';
import { ProgressBarModule } from 'primeng/progressbar';
import { MessageService } from 'primeng/api';
import { Api } from '../../core/api';
import { CuratedModel } from '../../core/types';

interface DownloadState { status: string; bytes_done: number; local_path?: string | null; error?: string | null; }

@Component({
  selector: 'app-models-page',
  imports: [DecimalPipe, NgTemplateOutlet, FormsModule, ButtonModule, InputTextModule, TagModule, ProgressBarModule],
  template: `
    <section class="page">
      <div class="head">
        <h1 class="title">النماذج <code class="ltr">models</code></h1>
        <p class="muted sub">ابحث في <code class="ltr">HuggingFace</code>، نزّل النموذج الأساسي محليًا، وتابع التقدّم.</p>
      </div>

      <!-- search -->
      <div class="search glass">
        <i class="pi pi-search"></i>
        <input pInputText [(ngModel)]="query" (keydown.enter)="search()" placeholder="ابحث: Qwen3, DeepSeek, Arabic …" class="grow ltr" />
        <p-button label="بحث" icon="pi pi-search" [loading]="searching()" (onClick)="search()" />
      </div>

      @if (results().length) {
        <div class="block">
          <h3 class="h">نتائج البحث</h3>
          <div class="rows">
            @for (r of results(); track r.repo_id) {
              <div class="row glass">
                <div class="info">
                  <span class="ltr repo">{{ r.repo_id }}</span>
                  <span class="meta dim ltr">
                    @if (r.downloads != null) { <span><i class="pi pi-download"></i> {{ r.downloads | number }}</span> }
                    @if (r.likes != null) { <span><i class="pi pi-heart"></i> {{ r.likes }}</span> }
                  </span>
                </div>
                <ng-container [ngTemplateOutlet]="dl" [ngTemplateOutletContext]="{ $implicit: r.repo_id }" />
              </div>
            }
          </div>
        </div>
      }

      <!-- curated -->
      <div class="block">
        <h3 class="h">مختارة للعربية</h3>
        <div class="rows">
          @for (m of curated(); track m.repo_id) {
            <div class="row glass">
              <div class="info">
                <span class="ltr repo">{{ m.label }}</span>
                @if (m.recommended) { <p-tag value="موصى به" severity="success" /> }
                <span class="badges">
                  <span class="b">{{ m.params }}</span><span class="b ltr">{{ m.context }}</span>
                  <span class="b">عربي: {{ m.arabic }}</span><span class="b ltr">{{ m.license }}</span>
                </span>
              </div>
              <ng-container [ngTemplateOutlet]="dl" [ngTemplateOutletContext]="{ $implicit: m.repo_id }" />
            </div>
          }
        </div>
      </div>

      <!-- local -->
      <div class="block">
        <h3 class="h">المحمَّلة محليًا</h3>
        @if (local().length) {
          <div class="rows">
            @for (l of local(); track l.repo_id) {
              <div class="row glass">
                <div class="info"><span class="ltr repo">{{ l.repo_id }}</span></div>
                <span class="ok"><i class="pi pi-check-circle"></i> {{ gb(l.bytes) }} GB</span>
              </div>
            }
          </div>
        } @else { <p class="muted dim">لا نماذج محمَّلة بعد.</p> }
      </div>
    </section>

    <!-- download cells rendered via template refs -->
    <ng-template #dl let-repo>
      @if (dlState(repo); as st) {
        @if (st.status === 'downloading' || st.status === 'pending') {
          <div class="dl">
            <p-progressBar mode="indeterminate" styleClass="pb" />
            <span class="dim ltr small">{{ gb(st.bytes_done) }} GB…</span>
          </div>
        } @else if (st.status === 'done') {
          <span class="ok"><i class="pi pi-check-circle"></i> محمّل</span>
        } @else if (st.status === 'error') {
          <span class="err" [title]="st.error || ''"><i class="pi pi-times-circle"></i> فشل</span>
        } @else {
          <p-button label="تنزيل" icon="pi pi-download" size="small" [outlined]="true" (onClick)="download(repo)" />
        }
      } @else {
        <p-button label="تنزيل" icon="pi pi-download" size="small" [outlined]="true" (onClick)="download(repo)" />
      }
    </ng-template>
  `,
  styles: [`
    .page { max-width: 1000px; margin: 0 auto; padding: 0.4rem 0.6rem; }
    .title { font-size: 1.9rem; margin: 0 0 0.2rem; }
    .sub { margin: 0 0 1.2rem; font-size: 0.9rem; }
    .search { display: flex; align-items: center; gap: 0.6rem; padding: 0.6rem 0.9rem; margin-bottom: 1.3rem; }
    .search .grow { flex: 1; }
    .block { margin-bottom: 1.5rem; }
    .h { font-size: 1.05rem; margin: 0 0 0.6rem; }
    .rows { display: flex; flex-direction: column; gap: 0.5rem; }
    .row { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 0.7rem 1rem; }
    .info { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
    .repo { font-weight: 700; font-size: 0.9rem; }
    .meta { display: flex; gap: 0.7rem; font-size: 0.78rem; }
    .badges { display: flex; gap: 0.3rem; flex-wrap: wrap; }
    .badges .b { font-size: 0.66rem; padding: 0.1rem 0.4rem; border-radius: 6px; background: rgba(255,255,255,0.07); }
    .dl { display: flex; align-items: center; gap: 0.5rem; min-width: 160px; }
    .dl .pb { width: 110px; }
    .small { font-size: 0.72rem; }
    .ok { color: var(--ok); display: inline-flex; gap: 0.3rem; align-items: center; font-size: 0.85rem; }
    .err { color: var(--err); display: inline-flex; gap: 0.3rem; align-items: center; font-size: 0.85rem; }
  `],
})
export class ModelsPage implements OnInit {
  private api = inject(Api);
  private toast = inject(MessageService);

  readonly results = signal<any[]>([]);
  readonly curated = signal<CuratedModel[]>([]);
  readonly local = signal<any[]>([]);
  readonly searching = signal(false);
  private downloads = signal<Record<string, DownloadState>>({});
  query = '';
  private timers: Record<string, any> = {};

  ngOnInit(): void {
    this.api.curatedModels().subscribe((m) => this.curated.set(m));
    this.refreshLocal();
  }

  refreshLocal(): void { this.api.localModels().subscribe((l) => this.local.set(l)); }

  search(): void {
    if (!this.query.trim()) return;
    this.searching.set(true);
    this.api.searchModels(this.query.trim()).subscribe({
      next: (r) => { this.results.set(r); this.searching.set(false); },
      error: () => { this.searching.set(false); this.toast.add({ severity: 'error', summary: 'تعذّر البحث' }); },
    });
  }

  download(repo: string): void {
    this.setDl(repo, { status: 'pending', bytes_done: 0 });
    this.api.downloadModel(repo).subscribe({
      next: () => this.poll(repo),
      error: (e) => this.setDl(repo, { status: 'error', bytes_done: 0, error: String(e?.error?.detail ?? e.message) }),
    });
  }

  private poll(repo: string): void {
    clearInterval(this.timers[repo]);
    this.timers[repo] = setInterval(() => {
      this.api.downloadStatus(repo).subscribe((s) => {
        this.setDl(repo, s);
        if (s.status === 'done' || s.status === 'error') {
          clearInterval(this.timers[repo]);
          if (s.status === 'done') { this.refreshLocal(); this.toast.add({ severity: 'success', summary: 'اكتمل التنزيل', detail: repo }); }
        }
      });
    }, 1500);
  }

  dlState(repo: string): DownloadState | null {
    const fromMap = this.downloads()[repo];
    if (fromMap) return fromMap;
    if (this.local().some((l) => l.repo_id === repo)) return { status: 'done', bytes_done: 0 };
    return null;
  }
  private setDl(repo: string, st: DownloadState): void { this.downloads.set({ ...this.downloads(), [repo]: st }); }

  gb(bytes: number): string { return (bytes / 1e9).toFixed(2); }
}
