import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { TagModule } from 'primeng/tag';
import { Api } from '../../core/api';
import { DebugStatus } from '../../core/types';

@Component({
  selector: 'app-debug-page',
  imports: [DecimalPipe, RouterLink, TagModule],
  template: `
    <section class="max-w-4xl mx-auto px-4 py-2">
      <div class="mb-5">
        <h1 class="text-2xl font-semibold m-0 mb-1">الحالة والتشخيص <code class="ltr">debug</code></h1>
        <p class="text-neutral-500 text-sm m-0">لقطة حيّة للعتاد والـ engine والتنزيلات والتدريبات وسجلّ الخادم — تتحدّث كل 3 ثوانٍ.</p>
      </div>

      @if (status(); as st) {
        <!-- environment -->
        <div class="flex flex-wrap gap-2 mb-5 text-xs">
          <span class="px-2.5 py-1 rounded-lg bg-neutral-100 dark:bg-neutral-800 ltr">Python {{ st.env.python }}</span>
          <span class="px-2.5 py-1 rounded-lg bg-neutral-100 dark:bg-neutral-800 ltr">torch {{ st.env.torch || '—' }}</span>
          <span class="px-2.5 py-1 rounded-lg bg-neutral-100 dark:bg-neutral-800 ltr">transformers {{ st.env.transformers || '—' }}</span>
          <p-tag [value]="st.env.ml_available ? 'ML stack جاهز' : 'ML stack غير مثبّت'" [severity]="st.env.ml_available ? 'success' : 'warn'" />
          <span class="px-2.5 py-1 rounded-lg bg-neutral-100 dark:bg-neutral-800"><span class="text-neutral-500">RAM</span> <span class="ltr font-semibold">{{ st.hardware.system_ram_gb | number:'1.0-1' }} GB</span></span>
          <span class="px-2.5 py-1 rounded-lg bg-neutral-100 dark:bg-neutral-800"><span class="text-neutral-500">VRAM (مُختار)</span> <span class="ltr font-semibold">{{ st.hardware.gpu_vram_gb | number:'1.0-1' }} GB</span></span>
        </div>

        <!-- live GPUs -->
        <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-4 mb-4">
          <h3 class="text-base font-semibold m-0 mb-3">بطاقات الرسوميات <code class="ltr">live</code></h3>
          @if (st.gpu_live.length) {
            <div class="flex flex-col gap-3">
              @for (g of st.gpu_live; track g.index) {
                <div class="flex flex-col gap-1.5">
                  <div class="flex items-center gap-2 text-sm flex-wrap">
                    <span class="ltr font-semibold">GPU {{ g.index }} · {{ g.name }}</span>
                    @if (isSelectedGpu(st, g.index)) { <p-tag value="مُختارة" severity="success" /> }
                    @if (g.temp_c != null) { <span class="text-xs text-neutral-400 ltr">{{ g.temp_c }}°C</span> }
                  </div>
                  <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div class="flex items-center gap-2 text-xs">
                      <span class="text-neutral-500 w-16 shrink-0 ltr">util</span>
                      <span class="flex-1 h-2 rounded bg-neutral-200 dark:bg-neutral-700 overflow-hidden">
                        <span class="block h-full bg-blue-500 transition-all duration-500" [style.width.%]="g.util_pct ?? 0"></span>
                      </span>
                      <span class="text-neutral-400 ltr w-10 text-end">{{ g.util_pct ?? '—' }}%</span>
                    </div>
                    <div class="flex items-center gap-2 text-xs">
                      <span class="text-neutral-500 w-16 shrink-0 ltr">memory</span>
                      <span class="flex-1 h-2 rounded bg-neutral-200 dark:bg-neutral-700 overflow-hidden">
                        <span class="block h-full bg-emerald-500 transition-all duration-500" [style.width.%]="memPct(g)"></span>
                      </span>
                      <span class="text-neutral-400 ltr whitespace-nowrap">{{ g.mem_used_gb | number:'1.1-1' }}/{{ g.mem_total_gb | number:'1.0-0' }} GB</span>
                    </div>
                  </div>
                </div>
              }
            </div>
          } @else {
            <p class="text-neutral-400 text-sm m-0">لا <code class="ltr">GPU</code> مكتشف (أو تعذّرت قراءة الاستخدام الحي).</p>
          }
        </div>

        <!-- engine -->
        <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-4 mb-4">
          <h3 class="text-base font-semibold m-0 mb-3">محرّك الاستدلال <code class="ltr">engine</code></h3>
          <div class="flex flex-wrap gap-2 text-xs items-center">
            <p-tag [value]="st.engine['runtime_available'] ? 'runtime جاهز' : 'runtime غير متاح'" [severity]="st.engine['runtime_available'] ? 'success' : 'warn'" />
            <p-tag [value]="st.engine['loaded'] ? 'نموذج محمّل' : 'لا نموذج محمّل'" [severity]="st.engine['loaded'] ? 'info' : 'secondary'" />
            @if (st.engine['base_id']) { <code class="ltr px-2 py-0.5 rounded bg-neutral-100 dark:bg-neutral-800">{{ st.engine['base_id'] }}</code> }
            @if (st.engine['vram_used_gb'] != null) { <span class="text-neutral-400 ltr">VRAM {{ st.engine['vram_used_gb'] | number:'1.1-1' }}/{{ st.engine['vram_total_gb'] | number:'1.0-0' }} GB</span> }
          </div>
        </div>

        <!-- downloads -->
        <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-4 mb-4">
          <h3 class="text-base font-semibold m-0 mb-3">التنزيلات <code class="ltr">downloads</code></h3>
          @if (st.downloads.length) {
            <div class="flex flex-col gap-2">
              @for (d of st.downloads; track d.repo_type + ':' + d.repo_id) {
                <div class="flex items-center gap-3 text-sm flex-wrap">
                  <code class="ltr text-xs">{{ d.repo_id }}</code>
                  <span class="text-[0.66rem] px-1.5 py-0.5 rounded bg-neutral-100 dark:bg-neutral-800 ltr">{{ d.repo_type }}</span>
                  <p-tag [value]="d.status" [severity]="dlSev(d.status)" />
                  @if (d.status === 'downloading') { <span class="text-xs text-neutral-400 ltr">{{ d.percent }}%</span> }
                  @if (d.error) { <span class="text-xs text-red-500 ltr truncate max-w-64" [title]="d.error">{{ d.error }}</span> }
                </div>
              }
            </div>
          } @else { <p class="text-neutral-400 text-sm m-0">لا تنزيلات في هذه الجلسة.</p> }
        </div>

        <!-- active runs -->
        <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-4 mb-4">
          <h3 class="text-base font-semibold m-0 mb-3">تدريبات نشطة <code class="ltr">runs</code></h3>
          @if (st.active_runs.length) {
            <div class="flex flex-col gap-2">
              @for (r of st.active_runs; track r.id) {
                <a class="flex items-center gap-3 text-sm no-underline text-inherit hover:underline" [routerLink]="['/projects', r.project_id]">
                  <span class="font-semibold">{{ r.name }}</span>
                  <p-tag [value]="r.status" severity="info" />
                  @if (r.pid) { <span class="text-xs text-neutral-400 ltr">PID {{ r.pid }}</span> }
                </a>
              }
            </div>
          } @else { <p class="text-neutral-400 text-sm m-0">لا تدريب جارٍ الآن.</p> }
        </div>

        <!-- backend logs -->
        <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-4">
          <h3 class="text-base font-semibold m-0 mb-3">سجلّ الخادم <code class="ltr">backend log</code></h3>
          <div class="ltr h-72 overflow-auto rounded-lg bg-neutral-950 text-neutral-200 text-xs leading-relaxed p-3 whitespace-pre-wrap">
            @for (l of logs(); track $index) { <div>{{ l }}</div> }
            @if (logs().length === 0) { <div class="text-neutral-500">no log lines yet…</div> }
          </div>
        </div>
      } @else {
        <p class="text-neutral-400">…جارٍ القراءة</p>
      }
    </section>
  `,
})
export class DebugPage implements OnInit, OnDestroy {
  private api = inject(Api);

  readonly status = signal<DebugStatus | null>(null);
  readonly logs = signal<string[]>([]);
  private timer: any = null;

  ngOnInit(): void {
    this.refresh();
    this.timer = setInterval(() => this.refresh(), 3000);
  }
  ngOnDestroy(): void { clearInterval(this.timer); }

  private refresh(): void {
    this.api.debugStatus().subscribe({ next: (s) => this.status.set(s), error: () => {} });
    this.api.debugLogs(200).subscribe({ next: (r) => this.logs.set(r.lines), error: () => {} });
  }

  isSelectedGpu(st: DebugStatus, index: number): boolean {
    return (st.hardware.selected_gpus ?? []).some((g) => g.index === index);
  }
  memPct(g: { mem_used_gb: number | null; mem_total_gb: number | null }): number {
    if (!g.mem_total_gb || g.mem_used_gb == null) return 0;
    return Math.round((g.mem_used_gb / g.mem_total_gb) * 100);
  }
  dlSev(s: string): 'success' | 'info' | 'warn' | 'danger' | 'secondary' {
    return s === 'done' ? 'success' : s === 'downloading' ? 'info' : s === 'error' ? 'danger' : 'secondary';
  }
}
