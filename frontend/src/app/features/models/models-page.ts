import { Component, OnInit, inject, signal } from '@angular/core';
import { DecimalPipe, NgTemplateOutlet } from '@angular/common';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { TagModule } from 'primeng/tag';
import { ProgressBarModule } from 'primeng/progressbar';
import { MessageService } from 'primeng/api';
import { Api } from '../../core/api';
import { DatasetHit, HubModel } from '../../core/types';

interface DownloadState {
  status: string;
  bytes_done: number;
  total_bytes?: number;
  percent?: number;
  local_path?: string | null;
  error?: string | null;
}

@Component({
  selector: 'app-models-page',
  imports: [DecimalPipe, NgTemplateOutlet, RouterLink, FormsModule, ButtonModule, InputTextModule, TagModule, ProgressBarModule],
  template: `
    <section class="max-w-4xl mx-auto px-4 py-2">
      <div class="mb-5">
        <h1 class="text-2xl font-semibold m-0 mb-1">النماذج <code class="ltr">models</code></h1>
        <p class="text-neutral-500 text-sm m-0">ابحث في <code class="ltr">HuggingFace</code>، نزّل النموذج الأساسي محليًا، وتابع التقدّم.</p>
      </div>

      <!-- token hint → settings -->
      <a routerLink="/settings"
         class="flex items-center gap-2 px-3 py-2 mb-5 rounded-lg border border-neutral-200 dark:border-neutral-800 text-sm text-neutral-600 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-800/50 no-underline transition-colors">
        <i class="pi pi-key text-neutral-400"></i>
        لإدارة رمز <code class="ltr">HuggingFace</code> (للنماذج/المجموعات الخاصة) افتح <span class="text-blue-600 dark:text-blue-400">الإعدادات</span>
        <i class="pi pi-arrow-left ms-auto text-xs text-neutral-400"></i>
      </a>

      <!-- search -->
      <div class="flex items-center gap-2 px-3 py-2 mb-5 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900">
        <i class="pi pi-search text-neutral-400"></i>
        <input pInputText [(ngModel)]="query" (keydown.enter)="search()" placeholder="ابحث: Qwen3, DeepSeek, Arabic …" class="flex-1 min-w-0 border-0 bg-transparent ltr" />
        <p-button label="بحث" icon="pi pi-search" [loading]="searching()" (onClick)="search()" size="small" />
      </div>

      @if (results().length) {
        <div class="mb-6">
          <h3 class="text-base font-semibold m-0 mb-2">نتائج البحث</h3>
          <div class="flex flex-col gap-2">
            @for (r of results(); track r.repo_id) {
              <div class="flex items-center justify-between gap-4 px-4 py-3 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900">
                <div class="flex items-center gap-2 flex-wrap min-w-0">
                  <span class="ltr font-semibold text-sm truncate">{{ r.repo_id }}</span>
                  <span class="flex gap-3 text-xs text-neutral-400 ltr">
                    @if (r.downloads != null) { <span><i class="pi pi-download"></i> {{ r.downloads | number }}</span> }
                    @if (r.likes != null) { <span><i class="pi pi-heart"></i> {{ r.likes }}</span> }
                  </span>
                </div>
                <ng-container [ngTemplateOutlet]="dl" [ngTemplateOutletContext]="{ $implicit: r.repo_id, type: 'model' }" />
              </div>
            }
          </div>
        </div>
      }

      <!-- dataset search (corpus browser) -->
      <div class="mb-6">
        <h3 class="text-base font-semibold m-0 mb-1">مجموعات البيانات <code class="ltr">datasets</code></h3>
        <p class="text-neutral-400 text-xs mb-2">ابحث في كوربوس <code class="ltr">HuggingFace</code>. تُستخدم لتدريب نموذج من الصفر (اخترها داخل معالج الإنشاء).</p>
        <div class="flex items-center gap-2 px-3 py-2 mb-3 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900">
          <i class="pi pi-search text-neutral-400"></i>
          <input pInputText [(ngModel)]="dsQuery" (keydown.enter)="searchDatasets()" placeholder="ابحث: wikitext, arabic, oscar …" class="flex-1 min-w-0 border-0 bg-transparent ltr" />
          <p-button label="بحث" icon="pi pi-search" [loading]="dsSearching()" (onClick)="searchDatasets()" size="small" />
        </div>
        @if (dsResults().length) {
          <div class="flex flex-col gap-2">
            @for (d of dsResults(); track d.repo_id) {
              <div class="flex items-center justify-between gap-4 px-4 py-3 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900">
                <div class="flex items-center gap-2 flex-wrap min-w-0">
                  <span class="ltr font-semibold text-sm truncate">{{ d.repo_id }}</span>
                  <span class="flex gap-3 text-xs text-neutral-400 ltr">
                    @if (d.downloads != null) { <span><i class="pi pi-download"></i> {{ d.downloads | number }}</span> }
                    @if (d.likes != null) { <span><i class="pi pi-heart"></i> {{ d.likes }}</span> }
                  </span>
                </div>
                <div class="flex items-center gap-3 shrink-0">
                  <a class="ltr text-xs text-blue-600 dark:text-blue-400 no-underline hover:underline" [href]="'https://huggingface.co/datasets/' + d.repo_id" target="_blank" rel="noopener">HuggingFace ↗</a>
                  <ng-container [ngTemplateOutlet]="dl" [ngTemplateOutletContext]="{ $implicit: d.repo_id, type: 'dataset' }" />
                </div>
              </div>
            }
          </div>
        }
      </div>

      <!-- live from the HuggingFace API -->
      <div class="mb-6">
        <h3 class="text-base font-semibold m-0 mb-2">الأكثر تنزيلًا <code class="ltr">text-generation</code></h3>
        @if (offlineNote()) {
          <p class="text-amber-600 dark:text-amber-400 text-xs mb-2"><i class="pi pi-exclamation-triangle"></i> تعذّر الوصول إلى HuggingFace — تُعرض النماذج المحلية فقط.</p>
        }
        <div class="flex flex-col gap-2">
          @for (m of featured(); track m.repo_id) {
            <ng-container [ngTemplateOutlet]="hubRow" [ngTemplateOutletContext]="{ $implicit: m }" />
          } @empty { <p class="text-neutral-400 text-sm m-0">لا نتائج بعد.</p> }
        </div>
      </div>

      <div class="mb-6">
        <h3 class="text-base font-semibold m-0 mb-2">نماذج عربية</h3>
        <div class="flex flex-col gap-2">
          @for (m of featuredAr(); track m.repo_id) {
            <ng-container [ngTemplateOutlet]="hubRow" [ngTemplateOutletContext]="{ $implicit: m }" />
          } @empty { <p class="text-neutral-400 text-sm m-0">لا نتائج بعد.</p> }
        </div>
      </div>

      <!-- local -->
      <div class="mb-6">
        <h3 class="text-base font-semibold m-0 mb-2">المحمَّلة محليًا</h3>
        @if (local().length) {
          <div class="flex flex-col gap-2">
            @for (l of local(); track l.repo_id) {
              <div class="flex items-center justify-between gap-4 px-4 py-3 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900">
                <span class="ltr font-semibold text-sm">{{ l.repo_id }}</span>
                <span class="text-emerald-600 dark:text-emerald-400 inline-flex gap-1 items-center text-sm"><i class="pi pi-check-circle"></i> {{ gb(l.bytes) }} GB</span>
              </div>
            }
          </div>
        } @else { <p class="text-neutral-400">لا نماذج محمَّلة بعد.</p> }
      </div>
    </section>

    <!-- one hub-model row (featured sections) -->
    <ng-template #hubRow let-m>
      <div class="flex items-center justify-between gap-4 px-4 py-3 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900">
        <div class="flex items-center gap-2 flex-wrap min-w-0">
          <span class="ltr font-semibold text-sm truncate">{{ m.repo_id }}</span>
          @if (m.gated) { <p-tag value="gated" severity="warn" /> }
          <span class="flex gap-1 flex-wrap items-center">
            @if (m.params) { <span class="text-[0.66rem] px-1.5 py-0.5 rounded bg-neutral-100 dark:bg-neutral-800 ltr">{{ m.params }}</span> }
            @if (m.license) { <span class="text-[0.66rem] px-1.5 py-0.5 rounded bg-neutral-100 dark:bg-neutral-800 ltr">{{ m.license }}</span> }
            @if (m.downloads != null) { <span class="text-xs text-neutral-400 ltr"><i class="pi pi-download"></i> {{ m.downloads | number }}</span> }
          </span>
        </div>
        <ng-container [ngTemplateOutlet]="dl" [ngTemplateOutletContext]="{ $implicit: m.repo_id, type: 'model' }" />
      </div>
    </ng-template>

    <!-- download cells rendered via template refs -->
    <ng-template #dl let-repo let-type="type">
      @if (dlState(repo, type); as st) {
        @if (st.status === 'downloading' || st.status === 'pending') {
          <div class="flex items-center gap-2 min-w-[200px]">
            @if (st.total_bytes) {
              <p-progressBar [value]="st.percent ?? 0" [showValue]="false" styleClass="w-28" />
              <span class="text-neutral-400 ltr text-xs whitespace-nowrap">{{ gb(st.bytes_done) }}/{{ gb(st.total_bytes) }} GB</span>
            } @else {
              <p-progressBar mode="indeterminate" styleClass="w-28" />
              <span class="text-neutral-400 ltr text-xs whitespace-nowrap">{{ gb(st.bytes_done) }} GB…</span>
            }
          </div>
        } @else if (st.status === 'done') {
          <span class="text-emerald-600 dark:text-emerald-400 inline-flex gap-1 items-center text-sm"><i class="pi pi-check-circle"></i> محمّل</span>
        } @else if (st.status === 'error') {
          <span class="text-red-500 inline-flex gap-1 items-center text-sm" [title]="st.error || ''"><i class="pi pi-times-circle"></i> فشل</span>
        } @else {
          <p-button label="تنزيل" icon="pi pi-download" size="small" [outlined]="true" (onClick)="download(repo, type)" />
        }
      } @else {
        <p-button label="تنزيل" icon="pi pi-download" size="small" [outlined]="true" (onClick)="download(repo, type)" />
      }
    </ng-template>
  `,
})
export class ModelsPage implements OnInit {
  private api = inject(Api);
  private toast = inject(MessageService);

  readonly results = signal<any[]>([]);
  readonly featured = signal<HubModel[]>([]);
  readonly featuredAr = signal<HubModel[]>([]);
  readonly offlineNote = signal(false);
  readonly local = signal<any[]>([]);
  readonly searching = signal(false);
  readonly dsResults = signal<DatasetHit[]>([]);
  readonly dsSearching = signal(false);
  dsQuery = '';
  private downloads = signal<Record<string, DownloadState>>({});
  query = '';
  private timers: Record<string, any> = {};

  ngOnInit(): void {
    this.api.featuredModels().subscribe((m) => {
      this.featured.set(m);
      this.offlineNote.set(m.some((x) => x.source === 'local'));
    });
    this.api.featuredModels('ar').subscribe((m) =>
      this.featuredAr.set(m.filter((x) => x.source !== 'local')));
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

  searchDatasets(): void {
    if (!this.dsQuery.trim()) return;
    this.dsSearching.set(true);
    this.api.searchDatasets(this.dsQuery.trim()).subscribe({
      next: (r) => { this.dsResults.set(r); this.dsSearching.set(false); },
      error: () => { this.dsSearching.set(false); this.toast.add({ severity: 'error', summary: 'تعذّر البحث' }); },
    });
  }

  download(repo: string, type: string = 'model'): void {
    this.setDl(type, repo, { status: 'pending', bytes_done: 0 });
    const req = type === 'dataset' ? this.api.downloadDataset(repo) : this.api.downloadModel(repo);
    req.subscribe({
      next: () => this.poll(repo, type),
      error: (e) => this.setDl(type, repo, { status: 'error', bytes_done: 0, error: String(e?.error?.detail ?? e.message) }),
    });
  }

  private poll(repo: string, type: string): void {
    const k = this.key(type, repo);
    clearInterval(this.timers[k]);
    this.timers[k] = setInterval(() => {
      const obs = type === 'dataset' ? this.api.datasetDownloadStatus(repo) : this.api.downloadStatus(repo);
      obs.subscribe((s) => {
        this.setDl(type, repo, s);
        if (s.status === 'done' || s.status === 'error') {
          clearInterval(this.timers[k]);
          if (s.status === 'done') {
            if (type === 'model') this.refreshLocal();
            this.toast.add({ severity: 'success', summary: 'اكتمل التنزيل', detail: repo });
          }
        }
      });
    }, 1500);
  }

  private key(type: string, repo: string): string { return `${type}:${repo}`; }

  dlState(repo: string, type: string = 'model'): DownloadState | null {
    const fromMap = this.downloads()[this.key(type, repo)];
    if (fromMap) return fromMap;
    if (type === 'model' && this.local().some((l) => l.repo_id === repo)) return { status: 'done', bytes_done: 0 };
    return null;
  }
  private setDl(type: string, repo: string, st: DownloadState): void {
    this.downloads.set({ ...this.downloads(), [this.key(type, repo)]: st });
  }

  gb(bytes: number): string { return (bytes / 1e9).toFixed(2); }
}
