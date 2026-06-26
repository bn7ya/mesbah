import { Component, ElementRef, EventEmitter, Input, OnDestroy, OnInit, Output, ViewChild, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { InputNumberModule } from 'primeng/inputnumber';
import { SliderModule } from 'primeng/slider';
import { CheckboxModule } from 'primeng/checkbox';
import { ChartModule } from 'primeng/chart';
import { ProgressBarModule } from 'primeng/progressbar';
import { TagModule } from 'primeng/tag';
import { TooltipModule } from 'primeng/tooltip';
import { MessageService } from 'primeng/api';
import { Api } from '../../core/api';
import { MarkdownPipe } from '../../core/markdown.pipe';
import { AutoEnhanceEvent, AutoEnhanceLoop, RunStatus } from '../../core/types';

const STATUS_SEV: Record<RunStatus, 'secondary' | 'info' | 'success' | 'danger' | 'warn'> = {
  pending: 'secondary', preparing: 'info', running: 'info',
  completed: 'success', failed: 'danger', cancelled: 'warn',
};
const STATUS_AR: Record<RunStatus, string> = {
  pending: 'بانتظار', preparing: 'تحضير', running: 'يعمل',
  completed: 'مكتمل', failed: 'فشل', cancelled: 'أُلغي',
};
const PHASE_AR: Record<string, string> = {
  generating: 'تهيئة', asking: 'يطرح سؤالًا', answering: 'يُجيب',
  evaluating: 'يُقيّم', training: 'يتدرّب',
};
const DIMS = [
  { key: 'logic', label: 'المنطق', color: '#3b82f6' },
  { key: 'language', label: 'اللغة', color: '#10b981' },
  { key: 'context', label: 'السياق', color: '#8b5cf6' },
  { key: 'factuality', label: 'الهلوسة', color: '#f59e0b' },
] as const;

interface TItem {
  kind: 'gen' | 'ask' | 'answer' | 'correction' | 'eval' | 'turn' | 'training' | 'done' | 'error';
  generation?: number; turn?: number; round?: number; text?: string;
  scores?: Record<string, number>; approved?: boolean; rounds?: number;
  status?: string; num_examples?: number; reason?: string; message?: string;
}

@Component({
  selector: 'app-auto-enhance-panel',
  imports: [
    DatePipe, DecimalPipe, FormsModule, ButtonModule, InputTextModule, InputNumberModule,
    SliderModule, CheckboxModule, ChartModule, ProgressBarModule, TagModule, TooltipModule,
    MarkdownPipe,
  ],
  template: `
    <div class="grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-4">
      <!-- left: launcher + history -->
      <div class="flex flex-col gap-4">
        <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-4">
          <h3 class="m-0 mb-1 text-base font-semibold">حلقة تحسين تلقائي جديدة</h3>
          <p class="text-sm text-neutral-500 mb-3">النموذج يحاور نفسه: يسأل، يُجيب، يُقيّم إجابته (منطق، لغة، سياق، هلوسة)، يُصحّحها حتى تجتاز، ثم يتدرّب على ما اجتاز وينشئ إصدارًا جديدًا — ويُعيد الكرّة.</p>

          <input pInputText [(ngModel)]="loopName" placeholder="اسم الحلقة، مثال: تحسين المنطق" class="w-full mb-3" />

          <div class="grid grid-cols-2 gap-3 p-3 rounded-lg border border-neutral-200 dark:border-neutral-800 mb-3">
            <div class="flex flex-col gap-1"><label class="ltr text-xs text-neutral-500">الأجيال <code class="ltr">generations</code></label><p-inputNumber [(ngModel)]="generations" [min]="1" [max]="10" [showButtons]="true" styleClass="w-full" /></div>
            <div class="flex flex-col gap-1"><label class="ltr text-xs text-neutral-500">أدوار/جيل</label><p-inputNumber [(ngModel)]="turnsPerGeneration" [min]="1" [max]="50" [showButtons]="true" styleClass="w-full" /></div>
          </div>
          <div class="flex flex-col gap-1 mb-3"><label class="ltr text-xs text-neutral-500">أقصى جولات تصحيح</label><p-inputNumber [(ngModel)]="maxRounds" [min]="0" [max]="10" [showButtons]="true" styleClass="w-full" /></div>

          <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 p-3 mb-3">
            <span class="block text-sm font-semibold mb-2">حدود الاجتياز (0–10)</span>
            @for (d of dims; track d.key) {
              <div class="flex items-center gap-3 mb-2">
                <span class="min-w-[52px] text-sm" [style.color]="d.color">{{ d.label }}</span>
                <p-slider [(ngModel)]="thresholds[d.key]" [min]="0" [max]="10" [step]="1" styleClass="flex-1" />
                <span class="text-sm font-bold w-5 text-center ltr">{{ thresholds[d.key] }}</span>
              </div>
            }
          </div>

          <label class="flex items-center gap-2 text-sm mb-3 cursor-pointer"><p-checkbox [(ngModel)]="useTasks" [binary]="true" /> اشتقّ المواضيع من مهام المشروع</label>

          <button class="flex items-center gap-1.5 text-sm text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200 py-1 mb-1" (click)="showAdvanced.set(!showAdvanced())" type="button">
            <i class="pi" [class.pi-chevron-down]="showAdvanced()" [class.pi-chevron-left]="!showAdvanced()"></i>
            إعدادات <code class="ltr">QLoRA</code> المتقدمة
          </button>
          @if (showAdvanced()) {
            <div class="grid grid-cols-2 gap-3 p-3 rounded-lg border border-neutral-200 dark:border-neutral-800 mb-3">
              <div class="flex flex-col gap-1"><label class="ltr text-xs text-neutral-500">epochs</label><p-inputNumber [(ngModel)]="hyper.epochs" [min]="1" [max]="20" [showButtons]="true" styleClass="w-full" /></div>
              <div class="flex flex-col gap-1"><label class="ltr text-xs text-neutral-500">learning_rate</label><p-inputNumber [(ngModel)]="hyper.learning_rate" mode="decimal" [minFractionDigits]="0" [maxFractionDigits]="6" [step]="0.00005" styleClass="w-full" /></div>
              <div class="flex flex-col gap-1"><label class="ltr text-xs text-neutral-500">lora_r</label><p-inputNumber [(ngModel)]="hyper.lora_r" [min]="4" [max]="128" [step]="4" [showButtons]="true" styleClass="w-full" /></div>
              <div class="flex flex-col gap-1"><label class="ltr text-xs text-neutral-500">lora_alpha</label><p-inputNumber [(ngModel)]="hyper.lora_alpha" [min]="4" [max]="256" [step]="4" [showButtons]="true" styleClass="w-full" /></div>
              <div class="flex flex-col gap-1"><label class="ltr text-xs text-neutral-500">max_seq_len</label><p-inputNumber [(ngModel)]="hyper.max_seq_len" [min]="512" [max]="32768" [step]="512" styleClass="w-full" /></div>
              <div class="flex flex-col gap-1"><label class="ltr text-xs text-neutral-500">grad_accum_steps</label><p-inputNumber [(ngModel)]="hyper.grad_accum_steps" [min]="1" [max]="64" [showButtons]="true" styleClass="w-full" /></div>
            </div>
          }

          <p-button label="ابدأ التحسين التلقائي" icon="pi pi-sync" [disabled]="starting() || running()" [loading]="starting()" (onClick)="start()" styleClass="w-full" />
          <p class="flex gap-1.5 items-start mt-2 text-neutral-400 text-xs"><i class="pi pi-info-circle"></i> النموذج يتدرّب على مخرجاته الذاتية — راقب اتجاه الدرجات عبر الأجيال، وابقِ عدد الأجيال صغيرًا.</p>
        </div>

        <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-4">
          <h3 class="m-0 mb-1 text-base font-semibold">السجلّ</h3>
          @for (l of loops(); track l.id) {
            <button class="flex items-center gap-2 px-2.5 py-2 rounded-lg border text-start transition-colors"
              [class]="l.id === selected()?.id ? 'border-neutral-300 dark:border-neutral-600 bg-neutral-100 dark:bg-neutral-800' : 'border-transparent hover:bg-neutral-50 dark:hover:bg-neutral-800/50'"
              (click)="watch(l)" type="button">
              <span class="flex-1 text-sm truncate">{{ l.name }}</span>
              <p-tag [value]="statusAr(l.status)" [severity]="sev(l.status)" />
              <span class="text-neutral-400 ltr text-xs">{{ l.created_at | date:'short' }}</span>
            </button>
          }
          @if (loops().length === 0) { <p class="text-neutral-500 dark:text-neutral-400 text-xs">لا حلقات بعد.</p> }
        </div>
      </div>

      <!-- right: live dashboard -->
      <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-4 min-h-[520px] flex flex-col">
        @if (selected(); as l) {
          <div class="flex justify-between items-start mb-4">
            <div class="flex items-center gap-2.5">
              <h3 class="m-0 mb-1 text-base font-semibold">{{ l.name }}</h3>
              <p-tag [value]="statusAr(l.status)" [severity]="sev(l.status)" [icon]="l.status === 'running' ? 'pi pi-spin pi-spinner' : ''" />
            </div>
            @if (l.status === 'running' || l.status === 'preparing' || l.status === 'pending') {
              <p-button label="إيقاف" icon="pi pi-stop" severity="danger" [outlined]="true" size="small" (onClick)="cancel(l)" />
            }
          </div>

          <div class="grid grid-cols-2 md:grid-cols-4 gap-2.5 mb-3">
            <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-800/40 px-3 py-2.5 flex flex-col gap-0.5"><span class="text-xs text-neutral-500">الجيل / الدور</span><span class="text-base font-bold ltr">{{ live().generation ?? 0 }}.{{ live().turn ?? 0 }}</span></div>
            <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-800/40 px-3 py-2.5 flex flex-col gap-0.5"><span class="text-xs text-neutral-500">الطور</span><span class="text-base font-bold">{{ phaseAr(live().phase) }}</span></div>
            <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-800/40 px-3 py-2.5 flex flex-col gap-0.5"><span class="text-xs text-neutral-500">معتمد للتدريب</span><span class="text-base font-bold ltr">{{ approvedCount() }}</span></div>
            <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-800/40 px-3 py-2.5 flex flex-col gap-0.5"><span class="text-xs text-neutral-500"><code class="ltr">VRAM</code></span><span class="text-base font-bold ltr">{{ vram() != null ? (vram()! | number:'1.1-1') + ' GB' : '—' }}</span></div>
          </div>

          <div class="flex gap-1.5 flex-wrap mb-3">
            @for (d of dims; track d.key) {
              <p-tag [value]="d.label + ': ' + (live().scores?.[d.key] ?? '—')"
                     [severity]="scoreSev(l, d.key, live().scores?.[d.key])" />
            }
          </div>

          <div class="mb-3"><p-progressBar [value]="progressPct()" [showValue]="true" styleClass="w-full" /></div>

          <div class="mb-3">
            <p-chart type="line" [data]="chartData()" [options]="chartOptions" height="200px" />
          </div>

          <!-- live transcript -->
          <div class="flex-1 overflow-auto max-h-[420px] flex flex-col gap-2 pt-3 border-t border-neutral-200 dark:border-neutral-800">
            @for (it of transcript(); track $index) {
              @switch (it.kind) {
                @case ('gen') { <div class="flex items-center gap-1.5 text-sm font-semibold px-2.5 py-1.5 rounded-lg bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300"><i class="pi pi-flag"></i> الجيل {{ it.generation }}</div> }
                @case ('ask') {
                  <div class="flex gap-2 max-w-[92%] flex-row-reverse ms-auto"><div class="text-lg">🧑</div><div class="px-3 py-2 rounded-2xl bg-blue-50 dark:bg-blue-950/40"><p class="m-0 whitespace-pre-wrap leading-relaxed text-sm">{{ it.text }}</p></div></div>
                }
                @case ('answer') {
                  <div class="flex gap-2 max-w-[92%]"><div class="text-lg">🕯️</div><div class="px-3 py-2 rounded-2xl bg-neutral-100 dark:bg-neutral-800"><div class="text-sm leading-relaxed [&_h1]:text-base [&_h1]:font-bold [&_h2]:text-base [&_h2]:font-bold [&_h3]:font-bold [&_h1]:mt-2 [&_h2]:mt-2 [&_table]:w-full [&_table]:my-2 [&_table]:border-collapse [&_th]:border [&_td]:border [&_th]:border-neutral-300 [&_td]:border-neutral-300 dark:[&_th]:border-neutral-700 dark:[&_td]:border-neutral-700 [&_th]:p-1 [&_td]:p-1 [&_th]:text-start [&_td]:text-start [&_pre]:bg-neutral-100 dark:[&_pre]:bg-neutral-800 [&_pre]:p-2 [&_pre]:rounded [&_pre]:overflow-auto [&_pre]:ltr [&_pre]:text-left [&_code]:ltr [&_code]:bg-neutral-100 dark:[&_code]:bg-neutral-800 [&_code]:px-1 [&_code]:rounded" [innerHTML]="it.text | markdown"></div></div></div>
                }
                @case ('correction') {
                  <div class="flex gap-2 max-w-[92%]"><div class="text-lg">✨</div><div class="px-3 py-2 rounded-2xl bg-neutral-100 dark:bg-neutral-800 border border-dashed border-neutral-300 dark:border-neutral-600"><div class="text-neutral-400 text-xs mb-1">تصحيح · جولة {{ it.round }}</div><div class="text-sm leading-relaxed [&_h1]:text-base [&_h1]:font-bold [&_h2]:text-base [&_h2]:font-bold [&_h3]:font-bold [&_h1]:mt-2 [&_h2]:mt-2 [&_table]:w-full [&_table]:my-2 [&_table]:border-collapse [&_th]:border [&_td]:border [&_th]:border-neutral-300 [&_td]:border-neutral-300 dark:[&_th]:border-neutral-700 dark:[&_td]:border-neutral-700 [&_th]:p-1 [&_td]:p-1 [&_th]:text-start [&_td]:text-start [&_pre]:bg-neutral-100 dark:[&_pre]:bg-neutral-800 [&_pre]:p-2 [&_pre]:rounded [&_pre]:overflow-auto [&_pre]:ltr [&_pre]:text-left [&_code]:ltr [&_code]:bg-neutral-100 dark:[&_code]:bg-neutral-800 [&_code]:px-1 [&_code]:rounded" [innerHTML]="it.text | markdown"></div></div></div>
                }
                @case ('eval') {
                  <div class="flex gap-1.5 items-center flex-wrap ps-6">
                    @for (d of dims; track d.key) {
                      <p-tag [value]="d.label + ' ' + (it.scores?.[d.key] ?? '—')" [severity]="scoreSev(selected()!, d.key, it.scores?.[d.key])" />
                    }
                    @if (it.round) { <span class="text-neutral-400 text-xs">بعد جولة {{ it.round }}</span> }
                  </div>
                }
                @case ('turn') {
                  <div class="flex items-center gap-1.5 text-sm font-semibold px-2.5 py-1.5 rounded-lg" [class]="it.approved ? 'text-emerald-600 dark:text-emerald-400' : 'text-neutral-500'">
                    <i class="pi" [class.pi-check-circle]="it.approved" [class.pi-times-circle]="!it.approved"></i>
                    الدور {{ it.turn }} — {{ it.approved ? 'اجتاز ✓ (أُضيف للتدريب)' : 'لم يجتز (مستبعد)' }}
                  </div>
                }
                @case ('training') {
                  <div class="flex items-center gap-1.5 text-sm font-semibold px-2.5 py-1.5 rounded-lg bg-neutral-100 dark:bg-neutral-800">
                    <i class="pi pi-bolt"></i>
                    @if (it.reason) { تجاوز التدريب: لا أمثلة معتمدة }
                    @else if (it.status) { التدريب: {{ it.status }} }
                    @else { بدء التدريب على {{ it.num_examples }} مثالًا }
                  </div>
                }
                @case ('done') { <div class="flex items-center gap-1.5 text-sm font-semibold px-2.5 py-1.5 rounded-lg bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300"><i class="pi pi-flag-fill"></i> {{ it.text }}</div> }
                @case ('error') { <pre class="ltr bg-red-50 dark:bg-red-950/30 text-red-600 dark:text-red-400 p-2.5 rounded-lg text-xs max-h-40 overflow-auto whitespace-pre-wrap">{{ it.message }}</pre> }
              }
            }
            @if (transcript().length === 0) { <p class="text-neutral-500 dark:text-neutral-400 text-xs text-center">بانتظار أول حدث…</p> }
          </div>

          <div class="mt-3">
            <button class="flex items-center gap-1.5 text-xs text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200" (click)="showLogs.set(!showLogs())" type="button">
              <i class="pi" [class.pi-chevron-down]="showLogs()" [class.pi-chevron-left]="!showLogs()"></i>
              سجلّ التدريب <code class="ltr">terminal</code>
              @if (logs().length) { <span class="text-neutral-400">· {{ logs().length }}</span> }
            </button>
            @if (showLogs()) {
              <div #logBox class="ltr mt-2 h-48 overflow-auto rounded-lg bg-neutral-950 text-neutral-200 text-xs leading-relaxed p-3 whitespace-pre-wrap">
                @for (line of logs(); track $index) { <div>{{ line }}</div> }
                @if (logs().length === 0) { <div class="text-neutral-500">…لا خرج تدريب بعد (يظهر أثناء مرحلة fine-tune)</div> }
              </div>
            }
          </div>

          @if (l.status === 'failed' && l.error) { <pre class="ltr bg-red-50 dark:bg-red-950/30 text-red-600 dark:text-red-400 p-2.5 rounded-lg text-xs max-h-40 overflow-auto whitespace-pre-wrap">{{ l.error }}</pre> }
        } @else {
          <div class="flex flex-col items-center justify-center gap-2 text-neutral-500 min-h-[460px]">
            <span class="text-5xl">🔁</span>
            <p>اختر حلقة من السجلّ أو ابدأ حلقة تحسين تلقائي جديدة لمتابعتها مباشرةً.</p>
          </div>
        }
      </div>
    </div>
  `,
})
export class AutoEnhancePanel implements OnInit, OnDestroy {
  @Input() projectId!: string;
  @Output() changed = new EventEmitter<void>();
  private api = inject(Api);
  private toast = inject(MessageService);

  readonly dims = DIMS;
  readonly loops = signal<AutoEnhanceLoop[]>([]);
  readonly selected = signal<AutoEnhanceLoop | null>(null);
  readonly starting = signal(false);
  readonly live = signal<{ generation?: number; turn?: number; phase?: string; scores?: Record<string, number> }>({});
  readonly transcript = signal<TItem[]>([]);
  readonly chartData = signal<any>(this.emptyChart());
  readonly showAdvanced = signal(false);
  readonly vram = signal<number | null>(null);
  readonly logs = signal<string[]>([]);
  readonly showLogs = signal(true);
  @ViewChild('logBox') private logBox?: ElementRef<HTMLDivElement>;

  loopName = '';
  generations = 2;
  turnsPerGeneration = 5;
  maxRounds = 3;
  useTasks = true;
  thresholds: Record<string, number> = { logic: 7, language: 7, context: 7, factuality: 7 };
  hyper = { epochs: 3, learning_rate: 0.0002, lora_r: 16, lora_alpha: 32, max_seq_len: 4096, grad_accum_steps: 16 };

  private socket: WebSocket | null = null;
  private vramTimer: any = null;
  private turnLabels: string[] = [];
  private series: Record<string, number[]> = { logic: [], language: [], context: [], factuality: [] };

  chartOptions = {
    responsive: true, maintainAspectRatio: false, animation: { duration: 250 },
    plugins: { legend: { labels: { color: 'rgba(120,120,120,0.7)', boxWidth: 12, font: { size: 10 } } } },
    scales: {
      x: { ticks: { color: 'rgba(120,120,120,0.7)' }, grid: { color: 'rgba(120,120,120,0.12)' } },
      y: { min: 0, max: 10, ticks: { color: 'rgba(120,120,120,0.7)' }, grid: { color: 'rgba(120,120,120,0.12)' } },
    },
  };

  ngOnInit(): void {
    this.loadLoops();
    this.api.getProject(this.projectId).subscribe((p) => {
      const c = (p.default_train_config ?? {}) as Record<string, number>;
      const h = this.hyper as unknown as Record<string, number>;
      for (const k of Object.keys(h)) if (c[k] != null) h[k] = c[k];
    });
    this.pollVram();
    this.vramTimer = setInterval(() => this.pollVram(), 3000);
  }
  ngOnDestroy(): void { this.socket?.close(); if (this.vramTimer) clearInterval(this.vramTimer); }

  private pollVram(): void {
    this.api.system().subscribe({
      next: (s) => this.vram.set(s.engine?.vram_used_gb ?? null),
      error: () => {},
    });
  }

  running(): boolean {
    const l = this.selected();
    return !!l && (l.status === 'running' || l.status === 'preparing' || l.status === 'pending');
  }

  loadLoops(): void {
    this.api.listAutoEnhanceLoops(this.projectId).subscribe((ls) => {
      this.loops.set(ls);
      if (!this.selected()) {
        const active = ls.find((x) => x.status === 'running' || x.status === 'preparing' || x.status === 'pending');
        if (active) this.watch(active);
      }
    });
  }

  start(): void {
    this.starting.set(true);
    const name = this.loopName.trim() || `loop-${this.loops().length + 1}`;
    this.api.createAutoEnhanceLoop(this.projectId, {
      name,
      generations: this.generations,
      turns_per_generation: this.turnsPerGeneration,
      thresholds: { ...this.thresholds },
      max_correction_rounds: this.maxRounds,
      topic_source: this.useTasks ? 'tasks' : 'free',
      hyperparams: { ...this.hyper },
    }).subscribe({
      next: (l) => {
        this.starting.set(false);
        this.loopName = '';
        this.loadLoops();
        this.watch(l);
      },
      error: (e) => {
        this.starting.set(false);
        const detail = String(e?.error?.detail ?? e?.message ?? e);
        this.toast.add({ severity: e?.status === 409 ? 'warn' : 'error', summary: 'تعذّر بدء الحلقة', detail, life: 6000 });
      },
    });
  }

  watch(l: AutoEnhanceLoop): void {
    this.selected.set(l);
    this.resetView();
    this.live.set({ generation: l.progress?.generation, turn: l.progress?.turn, phase: l.progress?.phase });
    this.socket?.close();
    if (l.status === 'running' || l.status === 'preparing' || l.status === 'pending') {
      this.connect(l.id);
    } else {
      this.api.getAutoEnhanceLoop(l.id).subscribe((fresh) => this.selected.set(fresh));
    }
  }

  private connect(loopId: string): void {
    const sock = this.api.autoEnhanceSocket(loopId);
    this.socket = sock;
    sock.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === 'event') this.onEvent(msg.data as AutoEnhanceEvent);
      else if (msg.type === 'status') this.onStatus(msg.data);
      else if (msg.type === 'log') this.onLog(msg.data?.line ?? '');
    };
    sock.onerror = () => {};
  }

  private push(it: TItem): void { this.transcript.set([...this.transcript(), it]); }

  private onLog(line: string): void {
    if (!line) return;
    const next = [...this.logs(), line];
    if (next.length > 500) next.splice(0, next.length - 500);
    this.logs.set(next);
    queueMicrotask(() => { const el = this.logBox?.nativeElement; if (el) el.scrollTop = el.scrollHeight; });
  }

  private onEvent(e: AutoEnhanceEvent): void {
    switch (e.type) {
      case 'generation_start':
        this.live.set({ ...this.live(), generation: e.generation, turn: 0, phase: 'generating' });
        this.push({ kind: 'gen', generation: e.generation });
        break;
      case 'turn_start':
        this.live.set({ ...this.live(), generation: e.generation, turn: e.turn, phase: 'asking' });
        break;
      case 'ask':
        this.push({ kind: 'ask', text: e.text });
        break;
      case 'answer':
        this.live.set({ ...this.live(), phase: 'evaluating' });
        this.push({ kind: 'answer', text: e.text });
        break;
      case 'evaluation':
        this.live.set({ ...this.live(), scores: e.scores });
        this.push({ kind: 'eval', scores: e.scores, round: e.round });
        break;
      case 'correction':
        this.push({ kind: 'correction', text: e.text, round: e.round });
        break;
      case 'turn_done':
        this.push({ kind: 'turn', turn: e.turn, approved: e.approved, scores: e.scores, rounds: e.rounds });
        this.pushChartPoint(e.generation, e.turn, e.scores);
        break;
      case 'training_start':
        this.live.set({ ...this.live(), phase: 'training' });
        this.push({ kind: 'training', num_examples: e.num_examples });
        break;
      case 'training_skipped':
        this.push({ kind: 'training', reason: e.reason });
        break;
      case 'generation_done':
        // (kept compact — the turn dividers already mark progress)
        break;
      case 'loop_done':
        this.push({ kind: 'done', text: e.status === 'completed' ? 'اكتملت الحلقة' : 'انتهت الحلقة' });
        break;
      case 'error':
        this.push({ kind: 'error', message: e.message });
        break;
    }
  }

  private onStatus(s: any): void {
    const cur = this.selected();
    if (cur) this.selected.set({ ...cur, status: s.status, progress: s.progress ?? cur.progress, results: s.results ?? cur.results, error: s.error ?? cur.error });
    if (s.progress) this.live.set({ ...this.live(), generation: s.progress.generation, turn: s.progress.turn, phase: s.progress.phase });
    if (['completed', 'failed', 'cancelled'].includes(s.status)) {
      this.socket?.close();
      this.loadLoops();
      if (cur) this.api.getAutoEnhanceLoop(cur.id).subscribe((fresh) => this.selected.set(fresh));
      if (s.status === 'completed') {
        this.toast.add({ severity: 'success', summary: 'اكتمل التحسين التلقائي', detail: 'أُنشئت إصدارات جديدة — راجع شجرة الإصدارات.' });
        this.changed.emit();
      } else if (s.status === 'failed') {
        this.toast.add({ severity: 'error', summary: 'فشلت الحلقة', detail: s.error ?? '', life: 8000 });
      } else {
        this.changed.emit();
      }
    }
  }

  cancel(l: AutoEnhanceLoop): void {
    this.api.cancelAutoEnhanceLoop(l.id).subscribe(() => this.loadLoops());
  }

  private pushChartPoint(gen: number | undefined, turn: number | undefined, scores: Record<string, number> | undefined): void {
    if (!scores) return;
    this.turnLabels.push(`ج${gen ?? '?'}.${turn ?? '?'}`);
    for (const d of DIMS) this.series[d.key].push(scores[d.key] ?? 0);
    this.chartData.set({
      labels: [...this.turnLabels],
      datasets: DIMS.map((d) => ({
        label: d.label, data: [...this.series[d.key]], borderColor: d.color,
        backgroundColor: d.color, tension: 0.35, borderWidth: 2, pointRadius: 2, fill: false,
      })),
    });
  }

  approvedCount(): number {
    const gens = (this.selected()?.results?.generations ?? []) as Array<Record<string, number>>;
    return gens.reduce((sum, g) => sum + (Number(g['approved']) || 0), 0);
  }

  progressPct(): number {
    const l = this.selected(); if (!l) return 0;
    const totalTurns = (l.config?.generations ?? 1) * (l.config?.turns_per_generation ?? 1);
    const g = this.live().generation ?? 0; const t = this.live().turn ?? 0;
    const done = Math.max(0, (g - 1)) * (l.config?.turns_per_generation ?? 1) + t;
    return totalTurns ? Math.min(100, Math.round((done / totalTurns) * 100)) : 0;
  }

  phaseAr(p?: string): string {
    if (!p) return '—';
    if (p.startsWith('correcting')) return 'يُصحّح';
    return PHASE_AR[p] ?? p;
  }
  statusAr(s: RunStatus): string { return STATUS_AR[s]; }
  sev(s: RunStatus) { return STATUS_SEV[s]; }
  scoreSev(l: AutoEnhanceLoop, dim: string, val: number | undefined): 'success' | 'danger' | 'secondary' {
    if (val == null) return 'secondary';
    const th = l.config?.thresholds?.[dim as keyof typeof l.config.thresholds] ?? 7;
    return val >= th ? 'success' : 'danger';
  }

  private resetView(): void {
    this.transcript.set([]);
    this.logs.set([]);
    this.turnLabels = [];
    this.series = { logic: [], language: [], context: [], factuality: [] };
    this.chartData.set(this.emptyChart());
  }
  private emptyChart() {
    return { labels: [], datasets: DIMS.map((d) => ({ label: d.label, data: [], borderColor: d.color, backgroundColor: d.color, tension: 0.35, borderWidth: 2, pointRadius: 2, fill: false })) };
  }
}
