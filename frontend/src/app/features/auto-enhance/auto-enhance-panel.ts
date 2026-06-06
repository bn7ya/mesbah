import { Component, EventEmitter, Input, OnDestroy, OnInit, Output, inject, signal } from '@angular/core';
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
  { key: 'logic', label: 'المنطق', color: '#cf7d5c' },
  { key: 'language', label: 'اللغة', color: '#6ea8a0' },
  { key: 'context', label: 'السياق', color: '#b08acf' },
  { key: 'factuality', label: 'الهلوسة', color: '#e6a981' },
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
    <div class="grid">
      <!-- left: launcher + history -->
      <div class="left">
        <div class="launch glass">
          <h3 class="h">حلقة تحسين تلقائي جديدة</h3>
          <p class="muted sub">النموذج يحاور نفسه: يسأل، يُجيب، يُقيّم إجابته (منطق، لغة، سياق، هلوسة)، يُصحّحها حتى تجتاز، ثم يتدرّب على ما اجتاز وينشئ إصدارًا جديدًا — ويُعيد الكرّة.</p>

          <input pInputText [(ngModel)]="loopName" placeholder="اسم الحلقة، مثال: تحسين المنطق" class="full" />

          <div class="row2">
            <div class="f"><label>الأجيال <code class="ltr">generations</code></label><p-inputNumber [(ngModel)]="generations" [min]="1" [max]="10" [showButtons]="true" /></div>
            <div class="f"><label>أدوار/جيل</label><p-inputNumber [(ngModel)]="turnsPerGeneration" [min]="1" [max]="50" [showButtons]="true" /></div>
          </div>
          <div class="f"><label>أقصى جولات تصحيح</label><p-inputNumber [(ngModel)]="maxRounds" [min]="0" [max]="10" [showButtons]="true" /></div>

          <div class="thresh">
            <span class="lbl">حدود الاجتياز (0–10)</span>
            @for (d of dims; track d.key) {
              <div class="th">
                <span class="th-l" [style.color]="d.color">{{ d.label }}</span>
                <p-slider [(ngModel)]="thresholds[d.key]" [min]="0" [max]="10" [step]="1" styleClass="th-s" />
                <span class="th-v ltr">{{ thresholds[d.key] }}</span>
              </div>
            }
          </div>

          <label class="chk"><p-checkbox [(ngModel)]="useTasks" [binary]="true" /> اشتقّ المواضيع من مهام المشروع</label>

          <button class="adv-toggle" (click)="showAdvanced.set(!showAdvanced())" type="button">
            <i class="pi" [class.pi-chevron-down]="showAdvanced()" [class.pi-chevron-left]="!showAdvanced()"></i>
            إعدادات <code class="ltr">QLoRA</code> المتقدمة
          </button>
          @if (showAdvanced()) {
            <div class="adv">
              <div class="f"><label>epochs</label><p-inputNumber [(ngModel)]="hyper.epochs" [min]="1" [max]="20" [showButtons]="true" /></div>
              <div class="f"><label>learning_rate</label><p-inputNumber [(ngModel)]="hyper.learning_rate" mode="decimal" [minFractionDigits]="0" [maxFractionDigits]="6" [step]="0.00005" /></div>
              <div class="f"><label>lora_r</label><p-inputNumber [(ngModel)]="hyper.lora_r" [min]="4" [max]="128" [step]="4" [showButtons]="true" /></div>
              <div class="f"><label>lora_alpha</label><p-inputNumber [(ngModel)]="hyper.lora_alpha" [min]="4" [max]="256" [step]="4" [showButtons]="true" /></div>
              <div class="f"><label>max_seq_len</label><p-inputNumber [(ngModel)]="hyper.max_seq_len" [min]="512" [max]="32768" [step]="512" /></div>
              <div class="f"><label>grad_accum_steps</label><p-inputNumber [(ngModel)]="hyper.grad_accum_steps" [min]="1" [max]="64" [showButtons]="true" /></div>
            </div>
          }

          <p-button label="ابدأ التحسين التلقائي" icon="pi pi-sync" [disabled]="starting() || running()" [loading]="starting()" (onClick)="start()" styleClass="full" />
          <p class="warn-t dim small"><i class="pi pi-info-circle"></i> النموذج يتدرّب على مخرجاته الذاتية — راقب اتجاه الدرجات عبر الأجيال، وابقِ عدد الأجيال صغيرًا.</p>
        </div>

        <div class="runs glass">
          <h3 class="h">السجلّ</h3>
          @for (l of loops(); track l.id) {
            <button class="run" [class.sel]="l.id === selected()?.id" (click)="watch(l)" type="button">
              <span class="rn">{{ l.name }}</span>
              <p-tag [value]="statusAr(l.status)" [severity]="sev(l.status)" />
              <span class="dim ltr small">{{ l.created_at | date:'short' }}</span>
            </button>
          }
          @if (loops().length === 0) { <p class="muted dim small">لا حلقات بعد.</p> }
        </div>
      </div>

      <!-- right: live dashboard -->
      <div class="dash glass">
        @if (selected(); as l) {
          <div class="dash-head">
            <div>
              <h3 class="h">{{ l.name }}</h3>
              <p-tag [value]="statusAr(l.status)" [severity]="sev(l.status)" [icon]="l.status === 'running' ? 'pi pi-spin pi-spinner' : ''" />
            </div>
            @if (l.status === 'running' || l.status === 'preparing' || l.status === 'pending') {
              <p-button label="إيقاف" icon="pi pi-stop" severity="danger" [outlined]="true" size="small" (onClick)="cancel(l)" />
            }
          </div>

          <div class="kpis">
            <div class="kpi"><span class="k">الجيل / الدور</span><span class="v ltr">{{ live().generation ?? 0 }}.{{ live().turn ?? 0 }}</span></div>
            <div class="kpi"><span class="k">الطور</span><span class="v">{{ phaseAr(live().phase) }}</span></div>
            <div class="kpi"><span class="k">معتمد للتدريب</span><span class="v ltr">{{ approvedCount() }}</span></div>
            <div class="kpi"><span class="k"><code class="ltr">VRAM</code></span><span class="v ltr">{{ vram() != null ? (vram()! | number:'1.1-1') + ' GB' : '—' }}</span></div>
          </div>

          <div class="scores-now">
            @for (d of dims; track d.key) {
              <p-tag [value]="d.label + ': ' + (live().scores?.[d.key] ?? '—')"
                     [severity]="scoreSev(l, d.key, live().scores?.[d.key])" />
            }
          </div>

          <p-progressBar [value]="progressPct()" [showValue]="true" styleClass="pbar" />

          <div class="chart-box">
            <p-chart type="line" [data]="chartData()" [options]="chartOptions" height="200px" />
          </div>

          <!-- live transcript -->
          <div class="stream">
            @for (it of transcript(); track $index) {
              @switch (it.kind) {
                @case ('gen') { <div class="divider gen"><i class="pi pi-flag"></i> الجيل {{ it.generation }}</div> }
                @case ('ask') {
                  <div class="msg user"><div class="avatar">🧑</div><div class="bubble glass"><p class="content">{{ it.text }}</p></div></div>
                }
                @case ('answer') {
                  <div class="msg assistant"><div class="avatar">🕯️</div><div class="bubble glass"><div class="content md" [innerHTML]="it.text | markdown"></div></div></div>
                }
                @case ('correction') {
                  <div class="msg assistant"><div class="avatar">✨</div><div class="bubble glass corr"><div class="corr-h dim small">تصحيح · جولة {{ it.round }}</div><div class="content md" [innerHTML]="it.text | markdown"></div></div></div>
                }
                @case ('eval') {
                  <div class="evrow">
                    @for (d of dims; track d.key) {
                      <p-tag [value]="d.label + ' ' + (it.scores?.[d.key] ?? '—')" [severity]="scoreSev(selected()!, d.key, it.scores?.[d.key])" />
                    }
                    @if (it.round) { <span class="dim small">بعد جولة {{ it.round }}</span> }
                  </div>
                }
                @case ('turn') {
                  <div class="divider turn" [class.ok]="it.approved" [class.no]="!it.approved">
                    <i class="pi" [class.pi-check-circle]="it.approved" [class.pi-times-circle]="!it.approved"></i>
                    الدور {{ it.turn }} — {{ it.approved ? 'اجتاز ✓ (أُضيف للتدريب)' : 'لم يجتز (مستبعد)' }}
                  </div>
                }
                @case ('training') {
                  <div class="divider train">
                    <i class="pi pi-bolt"></i>
                    @if (it.reason) { تجاوز التدريب: لا أمثلة معتمدة }
                    @else if (it.status) { التدريب: {{ it.status }} }
                    @else { بدء التدريب على {{ it.num_examples }} مثالًا }
                  </div>
                }
                @case ('done') { <div class="divider gen"><i class="pi pi-flag-fill"></i> {{ it.text }}</div> }
                @case ('error') { <pre class="err ltr">{{ it.message }}</pre> }
              }
            }
            @if (transcript().length === 0) { <p class="muted dim small center">بانتظار أول حدث…</p> }
          </div>

          @if (l.status === 'failed' && l.error) { <pre class="err ltr">{{ l.error }}</pre> }
        } @else {
          <div class="empty muted">
            <span class="big">🔁</span>
            <p>اختر حلقة من السجلّ أو ابدأ حلقة تحسين تلقائي جديدة لمتابعتها مباشرةً.</p>
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .grid { display: grid; grid-template-columns: 340px 1fr; gap: 1rem; }
    .left { display: flex; flex-direction: column; gap: 1rem; }
    .launch, .runs, .dash { padding: 1rem; }
    .h { margin: 0 0 0.4rem; font-size: 1.05rem; }
    .sub { font-size: 0.8rem; margin: 0 0 0.7rem; }
    .full, .pbar { width: 100%; }
    input.full { margin-bottom: 0.6rem; }
    .row2 { display: flex; gap: 0.6rem; }
    .f { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.5rem; }
    .f label { font-size: 0.8rem; color: var(--text-2); }
    .f ::ng-deep .p-inputnumber-input, .f ::ng-deep input { width: 110px; }
    .thresh { border: 1px solid var(--glass-border); border-radius: 12px; padding: 0.6rem 0.7rem; margin-bottom: 0.7rem; }
    .thresh .lbl { font-weight: 600; font-size: 0.82rem; display: block; margin-bottom: 0.5rem; }
    .th { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.45rem; }
    .th-l { font-size: 0.8rem; min-width: 52px; }
    .th ::ng-deep .th-s { flex: 1; }
    .th-v { font-size: 0.8rem; min-width: 18px; text-align: center; font-weight: 700; }
    .chk { display: flex; align-items: center; gap: 0.45rem; font-size: 0.85rem; margin-bottom: 0.7rem; cursor: pointer; }
    .adv-toggle { background: none; border: none; color: var(--text-2); cursor: pointer; display: flex; align-items: center; gap: 0.4rem; padding: 0.3rem 0; font-size: 0.85rem; margin-bottom: 0.4rem; }
    .adv-toggle:hover { color: var(--text-1); }
    .adv { display: flex; flex-direction: column; gap: 0.3rem; padding: 0.6rem; border: 1px solid var(--glass-border); border-radius: 12px; margin-bottom: 0.7rem; }
    .warn-t { display: flex; gap: 0.4rem; align-items: flex-start; margin: 0.4rem 0 0; }
    .small { font-size: 0.72rem; }
    .runs { display: flex; flex-direction: column; gap: 0.35rem; }
    .run { display: flex; align-items: center; gap: 0.6rem; padding: 0.55rem 0.6rem; border-radius: 10px; background: transparent; border: 1px solid transparent; cursor: pointer; color: var(--text-1); text-align: start; }
    .run:hover { background: var(--glass-bg); }
    .run.sel { background: var(--glass-bg-strong); border-color: var(--glass-border); }
    .run .rn { flex: 1; font-size: 0.86rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .dash { min-height: 520px; display: flex; flex-direction: column; }
    .dash-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.9rem; }
    .dash-head .h { display: inline-block; margin-inline-end: 0.6rem; }
    .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.6rem; margin-bottom: 0.7rem; }
    .kpi { background: var(--glass-bg); border: 1px solid var(--glass-border); border-radius: 12px; padding: 0.55rem 0.65rem; display: flex; flex-direction: column; gap: 0.2rem; }
    .kpi .k { font-size: 0.7rem; color: var(--text-2); }
    .kpi .v { font-size: 1rem; font-weight: 700; }
    .scores-now { display: flex; gap: 0.35rem; flex-wrap: wrap; margin-bottom: 0.7rem; }
    .chart-box { margin-bottom: 0.7rem; }
    .stream { flex: 1; overflow: auto; max-height: 420px; display: flex; flex-direction: column; gap: 0.6rem; padding: 0.3rem; border-top: 1px solid var(--glass-border); padding-top: 0.7rem; }
    .msg { display: flex; gap: 0.5rem; max-width: 92%; }
    .msg.user { flex-direction: row-reverse; margin-inline-start: auto; }
    .avatar { font-size: 1.1rem; }
    .bubble { padding: 0.55rem 0.75rem; border-radius: 14px; }
    .msg.user .bubble { background: var(--accent-soft); }
    .bubble.corr { border: 1px dashed var(--glass-border); }
    .corr-h { margin-bottom: 0.25rem; }
    .content { margin: 0; white-space: pre-wrap; line-height: 1.6; font-size: 0.88rem; }
    .content.md { white-space: normal; }
    .content.md :first-child { margin-top: 0; }
    .content.md :last-child { margin-bottom: 0; }
    .content.md h1, .content.md h2, .content.md h3 { line-height: 1.3; margin: 0.6rem 0 0.3rem; font-weight: 700; font-size: 0.98rem; }
    .content.md table { direction: rtl; border-collapse: collapse; width: 100%; margin: 0.5rem 0; font-size: 0.84rem; }
    .content.md th, .content.md td { border: 1px solid var(--glass-border); padding: 0.3rem 0.5rem; text-align: start; }
    .content.md th { background: var(--glass-bg); font-weight: 700; }
    .content.md code { font-family: var(--font-mono); direction: ltr; unicode-bidi: embed; background: var(--glass-bg); padding: 0.05em 0.3em; border-radius: 5px; }
    .content.md pre { background: var(--glass-bg); border: 1px solid var(--glass-border); border-radius: 10px; padding: 0.6rem; overflow: auto; direction: ltr; text-align: left; }
    .evrow { display: flex; gap: 0.3rem; align-items: center; flex-wrap: wrap; padding-inline-start: 1.6rem; }
    .divider { display: flex; align-items: center; gap: 0.45rem; font-size: 0.8rem; font-weight: 600; padding: 0.35rem 0.6rem; border-radius: 9px; }
    .divider.gen { background: var(--accent-soft); color: var(--accent); }
    .divider.turn.ok { color: var(--ok, #3aa17e); }
    .divider.turn.no { color: var(--text-2); }
    .divider.train { background: var(--glass-bg); color: var(--text-1); }
    .err { background: rgba(251,113,133,0.1); color: var(--err, #d9534f); padding: 0.6rem; border-radius: 10px; font-size: 0.72rem; max-height: 160px; overflow: auto; white-space: pre-wrap; }
    .center { text-align: center; }
    .empty { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 460px; gap: 0.5rem; }
    .empty .big { font-size: 2.6rem; }
    @media (max-width: 860px) { .grid { grid-template-columns: 1fr; } .kpis { grid-template-columns: 1fr 1fr; } }
  `],
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
    plugins: { legend: { labels: { color: 'rgba(74,56,47,0.75)', boxWidth: 12, font: { size: 10 } } } },
    scales: {
      x: { ticks: { color: 'rgba(74,56,47,0.5)' }, grid: { color: 'rgba(74,56,47,0.08)' } },
      y: { min: 0, max: 10, ticks: { color: 'rgba(74,56,47,0.5)' }, grid: { color: 'rgba(74,56,47,0.08)' } },
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
    };
    sock.onerror = () => {};
  }

  private push(it: TItem): void { this.transcript.set([...this.transcript(), it]); }

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
    this.turnLabels = [];
    this.series = { logic: [], language: [], context: [], factuality: [] };
    this.chartData.set(this.emptyChart());
  }
  private emptyChart() {
    return { labels: [], datasets: DIMS.map((d) => ({ label: d.label, data: [], borderColor: d.color, backgroundColor: d.color, tension: 0.35, borderWidth: 2, pointRadius: 2, fill: false })) };
  }
}
