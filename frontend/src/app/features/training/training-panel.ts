import { Component, EventEmitter, Input, OnDestroy, OnInit, Output, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { CheckboxModule } from 'primeng/checkbox';
import { ChartModule } from 'primeng/chart';
import { ProgressBarModule } from 'primeng/progressbar';
import { TagModule } from 'primeng/tag';
import { MessageService } from 'primeng/api';
import { Api } from '../../core/api';
import { MetricPoint, RunStatus, TrainingRun } from '../../core/types';

const STATUS_SEV: Record<RunStatus, 'secondary' | 'info' | 'success' | 'danger' | 'warn'> = {
  pending: 'secondary', preparing: 'info', running: 'info',
  completed: 'success', failed: 'danger', cancelled: 'warn',
};
const STATUS_AR: Record<RunStatus, string> = {
  pending: 'بانتظار', preparing: 'تحضير', running: 'يتدرّب',
  completed: 'مكتمل', failed: 'فشل', cancelled: 'أُلغي',
};

@Component({
  selector: 'app-training-panel',
  imports: [DatePipe, DecimalPipe, FormsModule, ButtonModule, InputTextModule, CheckboxModule, ChartModule, ProgressBarModule, TagModule],
  template: `
    <div class="grid">
      <!-- left: launcher + runs -->
      <div class="left">
        <div class="launch glass">
          <h3 class="h">جلسة تدريب جديدة</h3>
          <p class="muted sub">يبني مجموعة بيانات من الردود المعتمدة ثم يضبط النموذج بـ <code class="ltr">QLoRA</code> انطلاقًا من الإصدار النشط.</p>
          <div class="ds">
            <i class="pi pi-database"></i>
            <span>{{ preview() }} مثال جاهز للتدريب</span>
          </div>
          <input pInputText [(ngModel)]="runName" placeholder="اسم الإصدار، مثال: v1 — تحسين اللهجة" class="full" />
          <label class="chk"><p-checkbox [(ngModel)]="onlyCorrected" [binary]="true" /> الأمثلة المُصحّحة فقط</label>
          <p-button label="ابدأ التدريب" icon="pi pi-bolt" [disabled]="preview() === 0 || starting()" [loading]="starting()" (onClick)="start()" styleClass="full" />
          @if (preview() === 0) { <p class="warn-t"><i class="pi pi-info-circle"></i> صحّح واعتمد بعض الردود أولًا.</p> }
        </div>

        <div class="runs glass">
          <h3 class="h">السجلّ</h3>
          @for (r of runs(); track r.id) {
            <button class="run" [class.sel]="r.id === selected()?.id" (click)="watch(r)" type="button">
              <span class="rn">{{ r.name }}</span>
              <p-tag [value]="statusAr(r.status)" [severity]="sev(r.status)" />
              <span class="dim ltr small">{{ r.created_at | date:'short' }}</span>
            </button>
          }
          @if (runs().length === 0) { <p class="muted dim small">لا تدريبات بعد.</p> }
        </div>
      </div>

      <!-- right: live dashboard -->
      <div class="dash glass">
        @if (selected(); as r) {
          <div class="dash-head">
            <div>
              <h3 class="h">{{ r.name }}</h3>
              <p-tag [value]="statusAr(r.status)" [severity]="sev(r.status)" [icon]="r.status === 'running' ? 'pi pi-spin pi-spinner' : ''" />
            </div>
            @if (r.status === 'running' || r.status === 'preparing') {
              <p-button label="إيقاف" icon="pi pi-stop" severity="danger" [outlined]="true" size="small" (onClick)="cancel(r)" />
            }
          </div>

          <div class="kpis">
            <div class="kpi"><span class="k">الخطوة</span><span class="v ltr">{{ live().step ?? 0 }} / {{ totalSteps() || '—' }}</span></div>
            <div class="kpi"><span class="k">الخسارة <code class="ltr">loss</code></span><span class="v ltr">{{ live().loss != null ? (live().loss | number:'1.4-4') : '—' }}</span></div>
            <div class="kpi"><span class="k"><code class="ltr">lr</code></span><span class="v ltr">{{ live().learning_rate != null ? (live().learning_rate | number:'1.2-7') : '—' }}</span></div>
            <div class="kpi"><span class="k"><code class="ltr">VRAM</code></span><span class="v ltr">{{ live().vram_reserved_gb != null ? (live().vram_reserved_gb | number:'1.1-1') + ' GB' : '—' }}</span></div>
          </div>

          <p-progressBar [value]="progressPct()" [showValue]="true" styleClass="pbar" />

          <div class="chart-box">
            <p-chart type="line" [data]="chartData()" [options]="chartOptions" height="260px" />
          </div>

          @if (r.status === 'failed' && r.error) {
            <pre class="err ltr">{{ r.error }}</pre>
          }
          @if (r.status === 'completed') {
            <div class="done"><i class="pi pi-check-circle"></i> اكتمل التدريب وأصبح الإصدار الجديد نشطًا. راجع شجرة الإصدارات.</div>
          }
        } @else {
          <div class="empty muted">
            <span class="big">📈</span>
            <p>اختر تدريبًا من السجلّ أو ابدأ جلسة جديدة لمتابعة المنحنى مباشرةً.</p>
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .grid { display: grid; grid-template-columns: 330px 1fr; gap: 1rem; }
    .left { display: flex; flex-direction: column; gap: 1rem; }
    .launch, .runs, .dash { padding: 1rem; }
    .h { margin: 0 0 0.4rem; font-size: 1.05rem; }
    .sub { font-size: 0.8rem; margin: 0 0 0.7rem; }
    .ds { display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 0.7rem; border-radius: 10px; background: rgba(79,209,197,0.1); color: var(--accent); margin-bottom: 0.7rem; font-size: 0.9rem; }
    .full, .pbar { width: 100%; }
    input.full { margin-bottom: 0.6rem; }
    .chk { display: flex; align-items: center; gap: 0.45rem; font-size: 0.85rem; margin-bottom: 0.7rem; cursor: pointer; }
    .warn-t { color: var(--warn); font-size: 0.8rem; display: flex; gap: 0.4rem; align-items: center; }
    .runs { display: flex; flex-direction: column; gap: 0.35rem; }
    .run { display: flex; align-items: center; gap: 0.6rem; padding: 0.55rem 0.6rem; border-radius: 10px; background: transparent; border: 1px solid transparent; cursor: pointer; color: var(--text-1); text-align: start; }
    .run:hover { background: var(--glass-bg); }
    .run.sel { background: var(--glass-bg-strong); border-color: var(--glass-border); }
    .run .rn { flex: 1; font-size: 0.86rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .small { font-size: 0.72rem; }
    .dash { min-height: 460px; }
    .dash-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.9rem; }
    .dash-head .h { display: inline-block; margin-inline-end: 0.6rem; }
    .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.6rem; margin-bottom: 0.9rem; }
    .kpi { background: var(--glass-bg); border: 1px solid var(--glass-border); border-radius: 12px; padding: 0.6rem 0.7rem; display: flex; flex-direction: column; gap: 0.2rem; }
    .kpi .k { font-size: 0.72rem; color: var(--text-2); }
    .kpi .v { font-size: 1.05rem; font-weight: 700; }
    .chart-box { margin-top: 1rem; }
    .err { background: rgba(251,113,133,0.1); color: var(--err); padding: 0.7rem; border-radius: 10px; font-size: 0.72rem; max-height: 160px; overflow: auto; white-space: pre-wrap; }
    .done { color: var(--ok); display: flex; gap: 0.5rem; align-items: center; margin-top: 0.9rem; }
    .empty { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 420px; gap: 0.5rem; }
    .empty .big { font-size: 2.6rem; }
    @media (max-width: 860px) { .grid { grid-template-columns: 1fr; } .kpis { grid-template-columns: 1fr 1fr; } }
  `],
})
export class TrainingPanel implements OnInit, OnDestroy {
  @Input() projectId!: string;
  @Output() changed = new EventEmitter<void>();
  private api = inject(Api);
  private toast = inject(MessageService);

  readonly runs = signal<TrainingRun[]>([]);
  readonly selected = signal<TrainingRun | null>(null);
  readonly preview = signal(0);
  readonly starting = signal(false);
  readonly live = signal<MetricPoint>({});
  readonly chartData = signal<any>(this.emptyChart());

  runName = '';
  onlyCorrected = false;
  private socket: WebSocket | null = null;
  private steps: number[] = [];
  private losses: number[] = [];

  chartOptions = {
    responsive: true, maintainAspectRatio: false, animation: { duration: 250 },
    plugins: { legend: { labels: { color: 'rgba(255,255,255,0.7)' } } },
    scales: {
      x: { ticks: { color: 'rgba(255,255,255,0.4)' }, grid: { color: 'rgba(255,255,255,0.06)' }, title: { display: true, text: 'step', color: 'rgba(255,255,255,0.5)' } },
      y: { ticks: { color: 'rgba(255,255,255,0.4)' }, grid: { color: 'rgba(255,255,255,0.06)' }, title: { display: true, text: 'loss', color: 'rgba(255,255,255,0.5)' } },
    },
  };

  ngOnInit(): void { this.loadRuns(); this.loadPreview(); }
  ngOnDestroy(): void { this.socket?.close(); }

  loadPreview(): void { this.api.datasetPreview(this.projectId).subscribe((p) => this.preview.set(p.count)); }
  loadRuns(): void { this.api.listRuns(this.projectId).subscribe((r) => this.runs.set(r)); }

  start(): void {
    this.starting.set(true);
    const name = this.runName.trim() || `run-${this.runs().length + 1}`;
    this.api.createRun(this.projectId, { name, only_corrected: this.onlyCorrected, autostart: true }).subscribe({
      next: (r) => {
        this.starting.set(false);
        this.runName = '';
        this.loadRuns();
        if (r.status === 'failed') {
          this.toast.add({ severity: 'error', summary: 'تعذّر بدء التدريب', detail: r.error ?? '', life: 7000 });
        }
        this.watch(r);
      },
      error: (e) => { this.starting.set(false); this.toast.add({ severity: 'error', summary: 'خطأ', detail: String(e?.error?.detail ?? e.message) }); },
    });
  }

  watch(r: TrainingRun): void {
    this.selected.set(r);
    this.resetChart();
    this.socket?.close();
    this.live.set({ step: r.progress?.step ?? 0 });
    if (r.status === 'running' || r.status === 'preparing') {
      this.connect(r.id);
    } else {
      // terminal run: just refresh its detail
      this.api.getRun(r.id).subscribe((fresh) => this.selected.set(fresh));
    }
  }

  private connect(runId: string): void {
    const sock = this.api.trainingSocket(runId);
    this.socket = sock;
    sock.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === 'metric') this.onMetric(msg.data as MetricPoint);
      else if (msg.type === 'status') this.onStatus(msg.data);
    };
    sock.onerror = () => {};
  }

  private onMetric(p: MetricPoint): void {
    if (p.event === 'log' && p.step != null && p.loss != null) {
      this.steps.push(p.step);
      this.losses.push(p.loss);
      this.chartData.set({
        labels: [...this.steps],
        datasets: [{
          label: 'loss', data: [...this.losses], tension: 0.35, borderWidth: 2,
          borderColor: '#4fd1c5', backgroundColor: 'rgba(79,209,197,0.15)', fill: true, pointRadius: 0,
        }],
      });
    }
    this.live.set({ ...this.live(), ...p });
  }

  private onStatus(s: any): void {
    const cur = this.selected();
    if (cur) this.selected.set({ ...cur, status: s.status, progress: s.progress ?? cur.progress, error: s.error ?? cur.error });
    if (['completed', 'failed', 'cancelled'].includes(s.status)) {
      this.socket?.close();
      this.loadRuns();
      this.api.getRun(cur!.id).subscribe((fresh) => this.selected.set(fresh));
      if (s.status === 'completed') {
        this.toast.add({ severity: 'success', summary: 'اكتمل التدريب', detail: 'الإصدار الجديد أصبح نشطًا.' });
        this.changed.emit();
      } else if (s.status === 'failed') {
        this.toast.add({ severity: 'error', summary: 'فشل التدريب', detail: s.error ?? '', life: 8000 });
      }
    }
  }

  cancel(r: TrainingRun): void { this.api.cancelRun(r.id).subscribe(() => this.loadRuns()); }

  totalSteps(): number { return Number(this.selected()?.progress?.total_steps ?? this.live().total_steps ?? 0); }
  progressPct(): number {
    const total = this.totalSteps(); const step = this.live().step ?? 0;
    return total ? Math.min(100, Math.round((step / total) * 100)) : 0;
  }
  statusAr(s: RunStatus): string { return STATUS_AR[s]; }
  sev(s: RunStatus) { return STATUS_SEV[s]; }

  private resetChart(): void { this.steps = []; this.losses = []; this.chartData.set(this.emptyChart()); }
  private emptyChart() {
    return { labels: [], datasets: [{ label: 'loss', data: [], borderColor: '#4fd1c5', backgroundColor: 'rgba(79,209,197,0.15)', fill: true, tension: 0.35, pointRadius: 0 }] };
  }
}
