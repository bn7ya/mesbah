import { Component, ElementRef, EventEmitter, Input, OnDestroy, OnInit, Output, ViewChild, computed, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { InputNumberModule } from 'primeng/inputnumber';
import { SelectModule } from 'primeng/select';
import { CheckboxModule } from 'primeng/checkbox';
import { ChartModule } from 'primeng/chart';
import { ProgressBarModule } from 'primeng/progressbar';
import { TagModule } from 'primeng/tag';
import { DialogModule } from 'primeng/dialog';
import { MessageService } from 'primeng/api';
import { Api } from '../../core/api';
import { ArchitectureSpec, FeasibilityEstimate, MetricPoint, RunStatus, TrainingRun } from '../../core/types';

const STATUS_SEV: Record<RunStatus, 'secondary' | 'info' | 'success' | 'danger' | 'warn'> = {
  pending: 'secondary', preparing: 'info', running: 'info',
  completed: 'success', failed: 'danger', cancelled: 'warn',
};
const STATUS_AR: Record<RunStatus, string> = {
  pending: 'بانتظار', preparing: 'تحضير', running: 'يتدرّب',
  completed: 'مكتمل', failed: 'فشل', cancelled: 'أُلغي',
};

const FAMILIES = [
  { label: 'Qwen3 (dense)', value: 'qwen3' },
  { label: 'Llama (dense)', value: 'llama' },
  { label: 'Mistral (dense)', value: 'mistral' },
  { label: 'Qwen3-MoE (experts)', value: 'qwen3_moe' },
  { label: 'Mixtral (experts)', value: 'mixtral' },
];
const VERDICT_AR: Record<string, string> = {
  fits_vram: 'يسع الـ VRAM', cpu_offload: 'إزاحة إلى RAM', nvme_offload: 'إزاحة إلى NVMe',
  exceeds_disk: 'يتجاوز القرص',
};
const VERDICT_SEV: Record<string, 'success' | 'info' | 'warn' | 'danger'> = {
  fits_vram: 'success', cpu_offload: 'info', nvme_offload: 'warn', exceeds_disk: 'danger',
};

@Component({
  selector: 'app-training-panel',
  imports: [DatePipe, DecimalPipe, FormsModule, ButtonModule, InputTextModule, InputNumberModule, SelectModule, CheckboxModule, ChartModule, ProgressBarModule, TagModule, DialogModule],
  template: `
    <div class="grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-4">
      <!-- left: launcher + runs -->
      <div class="flex flex-col gap-4">
        @if (isScratch()) {
          <!-- ── from-scratch full-training launcher ── -->
          <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-4">
            <h3 class="m-0 mb-1 text-base font-semibold">تدريب النموذج من الصفر</h3>
            <p class="text-sm text-neutral-500 mb-3">تدريب <strong>كامل</strong> لكل المعاملات من أوزان عشوائية على كوربوس من <code class="ltr">HuggingFace</code> — لا يعتمد على الردود المعتمدة. أول تدريب يُنتج الإصدار الأول.</p>

            <!-- datasets (one or more) -->
            <div class="flex flex-col gap-1.5 mb-3">
              <div class="flex items-center gap-2 rounded-lg border border-neutral-200 dark:border-neutral-800 px-2.5 py-1.5">
                <i class="pi pi-search text-neutral-400"></i>
                <input pInputText class="flex-1 min-w-0 border-0 bg-transparent ltr" [(ngModel)]="dsQuery" (keydown.enter)="searchDs()" placeholder="أضف مجموعة بيانات: wikitext, arabic…" />
                <p-button label="بحث" [loading]="dsSearching()" (onClick)="searchDs()" size="small" />
              </div>
              @for (r of dsResults(); track r.repo_id) {
                <button class="flex items-center justify-between gap-2 px-2.5 py-2 rounded-lg border text-start transition-colors"
                        [class]="hasDs(r.repo_id) ? 'border-blue-400 ring-1 ring-blue-400/40 bg-blue-50/50 dark:bg-blue-950/20' : 'border-neutral-200 dark:border-neutral-800 hover:border-neutral-300 dark:hover:border-neutral-700'"
                        type="button" (click)="addDs(r.repo_id)">
                  <span class="ltr font-semibold text-[0.82rem] truncate">{{ r.repo_id }}</span>
                  <span class="text-neutral-400 ltr text-xs shrink-0">{{ hasDs(r.repo_id) ? '✓ مضافة' : '+ إضافة' }}</span>
                </button>
              }
              @for (d of datasets(); track d.repo) {
                <div class="flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-neutral-200 dark:border-neutral-800">
                  <span class="ltr font-semibold text-[0.82rem] flex-1 min-w-0 truncate">{{ d.repo }}</span>
                  <input pInputText class="ltr w-28 text-xs" [(ngModel)]="d.text_field" placeholder="text field" title="text field" />
                  <button class="text-red-500 hover:text-red-700 p-1 inline-flex" type="button" (click)="removeDs(d.repo)" title="إزالة"><i class="pi pi-times"></i></button>
                </div>
              }
              @if (datasets().length) {
                <span class="text-neutral-400 text-xs">{{ datasets().length }} مجموعة · حتى {{ scratchHyper.max_train_samples }} عيّنة (إجمالي بعد الدمج والخلط)</span>
              } @else {
                <span class="text-amber-600 dark:text-amber-400 text-xs">لم تُختَر مجموعة بيانات — أضف واحدة على الأقل.</span>
              }
            </div>

            <input pInputText [(ngModel)]="runName" placeholder="اسم الإصدار، مثال: v1 — التدريب الأولي" class="w-full mb-3" />

            <!-- feasibility readout -->
            <div class="flex flex-col gap-1.5 px-3 py-2 rounded-lg border mb-3"
                 [class]="archValid() ? 'border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-800/40' : 'border-red-300 dark:border-red-900 bg-red-50/60 dark:bg-red-950/20'">
              @if (estimating()) { <span class="text-neutral-500 text-xs">…تقدير الحجم</span> }
              @else if (estimate(); as e) {
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="text-xs">الحجم: <strong class="ltr">{{ e.params.total_params_human }}</strong></span>
                  @if (isMoe()) { <span class="text-neutral-400 ltr text-xs">active {{ e.params.active_params_human }}</span> }
                  <p-tag [value]="verdictAr(e.memory.verdict)" [severity]="verdictSev(e.memory.verdict)" />
                </div>
              }
              @for (w of archErrors(); track w) { <p class="text-xs m-0 text-red-600 dark:text-red-400">⛔ {{ w }}</p> }
            </div>

            <button class="flex items-center gap-1.5 text-sm text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200 py-1 mb-1" (click)="showAdvanced.set(!showAdvanced())" type="button">
              <i class="pi" [class.pi-chevron-down]="showAdvanced()" [class.pi-chevron-left]="!showAdvanced()"></i>
              المعمارية وإعدادات التدريب
            </button>
            @if (showAdvanced()) {
              <div class="grid grid-cols-2 gap-3 p-3 rounded-lg border border-neutral-200 dark:border-neutral-800 mb-3">
                @if (spec(); as s) {
                  <div class="flex flex-col gap-1"><label class="ltr text-xs text-neutral-500">family</label>
                    <p-select [options]="families" optionLabel="label" optionValue="value"
                              [(ngModel)]="s.family" (ngModelChange)="onArchChange()" appendTo="body" styleClass="w-full" /></div>
                  <div class="flex flex-col gap-1"><label class="ltr text-xs text-neutral-500">layers</label><p-inputNumber [(ngModel)]="s.num_hidden_layers" (ngModelChange)="onArchChange()" [min]="1" [max]="256" [showButtons]="true" styleClass="w-full" /></div>
                  <div class="flex flex-col gap-1"><label class="ltr text-xs text-neutral-500">hidden_size</label><p-inputNumber [(ngModel)]="s.hidden_size" (ngModelChange)="onArchChange()" [min]="8" [step]="64" [showButtons]="true" styleClass="w-full" /></div>
                  <div class="flex flex-col gap-1"><label class="ltr text-xs text-neutral-500">attn heads</label><p-inputNumber [(ngModel)]="s.num_attention_heads" (ngModelChange)="onArchChange()" [min]="1" [max]="256" [showButtons]="true" styleClass="w-full" /></div>
                  <div class="flex flex-col gap-1"><label class="ltr text-xs text-neutral-500">kv heads</label><p-inputNumber [(ngModel)]="s.num_key_value_heads" (ngModelChange)="onArchChange()" [min]="1" [max]="256" [showButtons]="true" styleClass="w-full" /></div>
                  <div class="flex flex-col gap-1"><label class="ltr text-xs text-neutral-500">vocab_size</label><p-inputNumber [(ngModel)]="s.vocab_size" (ngModelChange)="onArchChange()" [min]="1" [step]="1000" styleClass="w-full" /></div>
                  <div class="flex flex-col gap-1"><label class="ltr text-xs text-neutral-500">context</label><p-inputNumber [(ngModel)]="s.max_position_embeddings" (ngModelChange)="onArchChange()" [min]="8" [step]="512" styleClass="w-full" /></div>
                  @if (isMoe()) {
                    <div class="flex flex-col gap-1"><label class="ltr text-xs text-neutral-500">num_experts</label><p-inputNumber [(ngModel)]="s.num_experts" (ngModelChange)="onArchChange()" [min]="1" [max]="1024" [showButtons]="true" styleClass="w-full" /></div>
                    <div class="flex flex-col gap-1"><label class="ltr text-xs text-neutral-500">experts/token</label><p-inputNumber [(ngModel)]="s.num_experts_per_tok" (ngModelChange)="onArchChange()" [min]="1" [max]="1024" [showButtons]="true" styleClass="w-full" /></div>
                  }
                }
                <div class="col-span-2 h-px bg-neutral-200 dark:bg-neutral-800"></div>
                <div class="flex flex-col gap-1"><label class="ltr text-xs text-neutral-500">epochs</label><p-inputNumber [(ngModel)]="scratchHyper.epochs" [min]="1" [max]="50" [showButtons]="true" styleClass="w-full" /></div>
                <div class="flex flex-col gap-1"><label class="ltr text-xs text-neutral-500">learning_rate</label><p-inputNumber [(ngModel)]="scratchHyper.learning_rate" mode="decimal" [minFractionDigits]="0" [maxFractionDigits]="6" [step]="0.00005" styleClass="w-full" /></div>
                <div class="flex flex-col gap-1"><label class="ltr text-xs text-neutral-500">max_seq_len</label><p-inputNumber [(ngModel)]="scratchHyper.max_seq_len" [min]="128" [max]="32768" [step]="128" styleClass="w-full" /></div>
                <div class="flex flex-col gap-1"><label class="ltr text-xs text-neutral-500">max_train_samples</label><p-inputNumber [(ngModel)]="scratchHyper.max_train_samples" [min]="1" [step]="500" styleClass="w-full" /></div>
                <div class="flex flex-col gap-1"><label class="ltr text-xs text-neutral-500">grad_accum_steps</label><p-inputNumber [(ngModel)]="scratchHyper.grad_accum_steps" [min]="1" [max]="64" [showButtons]="true" styleClass="w-full" /></div>
              </div>
            }

            <p-button label="ابدأ التدريب" icon="pi pi-bolt" [disabled]="!canStartScratch()" [loading]="starting()" (onClick)="startScratch()" styleClass="w-full" />
            @if (!datasets().length) { <p class="flex items-center gap-1.5 text-amber-600 dark:text-amber-400 text-sm mt-2"><i class="pi pi-info-circle"></i> أضف مجموعة بيانات واحدة على الأقل أعلاه.</p> }
            @else if (!archValid()) { <p class="flex items-center gap-1.5 text-amber-600 dark:text-amber-400 text-sm mt-2"><i class="pi pi-info-circle"></i> صحّح المعمارية أعلاه قبل بدء التدريب.</p> }
            <p class="text-neutral-400 text-xs mt-2">⚠ الإزاحة <code class="ltr">ZeRO-Infinity</code> تُكمل التدريب رغم محدودية الذاكرة، لكنها لا توفّر الحوسبة/البيانات التي يحتاجها نموذج حقيقي — توقّع نموذجًا تجريبيًا وزمنًا طويلًا.</p>
          </div>
        } @else {
          <!-- ── QLoRA fine-tune launcher ── -->
          <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-4">
            <h3 class="m-0 mb-1 text-base font-semibold">جلسة تدريب جديدة</h3>
            <p class="text-sm text-neutral-500 mb-3">يبني مجموعة بيانات من الردود المعتمدة و/أو مجموعات <code class="ltr">HuggingFace</code>، ثم يضبط النموذج بـ <code class="ltr">QLoRA</code> انطلاقًا من الإصدار النشط.</p>
            <div class="flex items-center gap-2 px-3 py-2 rounded-lg bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 text-sm mb-3">
              <i class="pi pi-database"></i>
              <span>{{ preview() }} مثال جاهز للتدريب</span>
              <button class="ms-auto text-xs underline" (click)="openPreview()" type="button">معاينة</button>
            </div>
            <label class="flex items-center gap-2 text-sm mb-2 cursor-pointer"><p-checkbox [(ngModel)]="useCorrections" [binary]="true" /> استخدم الردود المعتمدة</label>

            <!-- optional HF datasets (trained alongside / instead of corrections) -->
            <div class="flex flex-col gap-1.5 mb-3">
              <div class="flex items-center gap-2 rounded-lg border border-neutral-200 dark:border-neutral-800 px-2.5 py-1.5">
                <i class="pi pi-search text-neutral-400"></i>
                <input pInputText class="flex-1 min-w-0 border-0 bg-transparent ltr" [(ngModel)]="dsQuery" (keydown.enter)="searchDs()" placeholder="أضف مجموعة بيانات من HuggingFace…" />
                <p-button label="بحث" [loading]="dsSearching()" (onClick)="searchDs()" size="small" />
              </div>
              @for (r of dsResults(); track r.repo_id) {
                <button class="flex items-center justify-between gap-2 px-2.5 py-2 rounded-lg border text-start transition-colors"
                        [class]="hasDs(r.repo_id) ? 'border-blue-400 ring-1 ring-blue-400/40 bg-blue-50/50 dark:bg-blue-950/20' : 'border-neutral-200 dark:border-neutral-800 hover:border-neutral-300 dark:hover:border-neutral-700'"
                        type="button" (click)="addDs(r.repo_id)">
                  <span class="ltr font-semibold text-[0.82rem] truncate">{{ r.repo_id }}</span>
                  <span class="text-neutral-400 ltr text-xs shrink-0">{{ hasDs(r.repo_id) ? '✓ مضافة' : '+ إضافة' }}</span>
                </button>
              }
              @for (d of datasets(); track d.repo) {
                <div class="flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-neutral-200 dark:border-neutral-800">
                  <span class="ltr font-semibold text-[0.82rem] flex-1 min-w-0 truncate">{{ d.repo }}</span>
                  <input pInputText class="ltr w-28 text-xs" [(ngModel)]="d.text_field" placeholder="text field" title="text field" />
                  <button class="text-red-500 hover:text-red-700 p-1 inline-flex" type="button" (click)="removeDs(d.repo)" title="إزالة"><i class="pi pi-times"></i></button>
                </div>
              }
              @if (datasets().length) {
                <span class="text-neutral-400 text-xs">{{ datasets().length }} مجموعة — الأعمدة المعروفة (<code class="ltr">messages/instruction/prompt/text</code>) تُحوَّل تلقائيًا.</span>
              }
            </div>

            <input pInputText [(ngModel)]="runName" placeholder="اسم الإصدار، مثال: v1 — تحسين اللهجة" class="w-full mb-3" />
            <label class="flex items-center gap-2 text-sm mb-3 cursor-pointer"><p-checkbox [(ngModel)]="onlyCorrected" [binary]="true" /> الأمثلة المُصحّحة فقط</label>

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
                <p class="col-span-2 text-neutral-400 text-xs m-0">القيم الافتراضية مضبوطة تلقائيًا حسب عتاد جهازك (VRAM/RAM المكتشفة). ارفع <code class="ltr">max_seq_len</code> بحذر.</p>
              </div>
            }

            <p-button label="ابدأ التدريب" icon="pi pi-bolt" [disabled]="!canStartFinetune()" [loading]="starting()" (onClick)="start()" styleClass="w-full" />
            @if (!canStartFinetune() && !starting()) { <p class="flex items-center gap-1.5 text-amber-600 dark:text-amber-400 text-sm mt-2"><i class="pi pi-info-circle"></i> صحّح واعتمد بعض الردود أولًا، أو أضف مجموعة بيانات من <code class="ltr">HuggingFace</code>.</p> }
          </div>
        }

        <div class="flex flex-col gap-1 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-4">
          <h3 class="m-0 mb-2 text-base font-semibold">السجلّ</h3>
          @for (r of runs(); track r.id) {
            <button class="flex items-center gap-2 px-2.5 py-2 rounded-lg border text-start transition-colors"
                    [class]="r.id === selected()?.id ? 'border-neutral-300 dark:border-neutral-600 bg-neutral-100 dark:bg-neutral-800' : 'border-transparent hover:bg-neutral-50 dark:hover:bg-neutral-800/50'"
                    (click)="watch(r)" type="button">
              <span class="flex-1 text-sm truncate">{{ r.name }}</span>
              <p-tag [value]="statusAr(r.status)" [severity]="sev(r.status)" />
              <span class="text-neutral-400 ltr text-xs">{{ r.created_at | date:'short' }}</span>
            </button>
          }
          @if (runs().length === 0) { <p class="text-neutral-400 text-xs">لا تدريبات بعد.</p> }
        </div>
      </div>

      <!-- right: live dashboard -->
      <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-4 min-h-[460px]">
        @if (selected(); as r) {
          <div class="flex justify-between items-start mb-4">
            <div class="flex items-center gap-2.5">
              <h3 class="m-0 text-base font-semibold">{{ r.name }}</h3>
              <p-tag [value]="statusAr(r.status)" [severity]="sev(r.status)" [icon]="r.status === 'running' ? 'pi pi-spin pi-spinner' : ''" />
            </div>
            @if (r.status === 'running' || r.status === 'preparing') {
              <p-button label="إيقاف" icon="pi pi-stop" severity="danger" [outlined]="true" size="small" (onClick)="cancel(r)" />
            }
          </div>

          <div class="grid grid-cols-2 md:grid-cols-4 gap-2.5 mb-4">
            <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-800/40 px-3 py-2.5 flex flex-col gap-0.5"><span class="text-xs text-neutral-500">الخطوة</span><span class="text-base font-bold ltr">{{ live().step ?? 0 }} / {{ totalSteps() || '—' }}</span></div>
            <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-800/40 px-3 py-2.5 flex flex-col gap-0.5"><span class="text-xs text-neutral-500">الخسارة <code class="ltr">loss</code></span><span class="text-base font-bold ltr">{{ live().loss != null ? (live().loss | number:'1.4-4') : '—' }}</span></div>
            <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-800/40 px-3 py-2.5 flex flex-col gap-0.5"><span class="text-xs text-neutral-500"><code class="ltr">lr</code></span><span class="text-base font-bold ltr">{{ live().learning_rate != null ? (live().learning_rate | number:'1.2-7') : '—' }}</span></div>
            <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-800/40 px-3 py-2.5 flex flex-col gap-0.5"><span class="text-xs text-neutral-500"><code class="ltr">VRAM</code></span><span class="text-base font-bold ltr">{{ live().vram_reserved_gb != null ? (live().vram_reserved_gb | number:'1.1-1') + ' GB' : '—' }}</span></div>
          </div>

          <p-progressBar [value]="progressPct()" [showValue]="true" styleClass="w-full" />

          <div class="mt-4">
            <p-chart type="line" [data]="chartData()" [options]="chartOptions" height="260px" />
          </div>

          <!-- live terminal logs (trainer stdout/stderr) -->
          <div class="mt-4">
            <button class="flex items-center gap-1.5 text-xs text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200" (click)="showLogs.set(!showLogs())" type="button">
              <i class="pi" [class.pi-chevron-down]="showLogs()" [class.pi-chevron-left]="!showLogs()"></i>
              سجلّ التدريب <code class="ltr">terminal</code>
              @if (logs().length) { <span class="text-neutral-400">· {{ logs().length }}</span> }
            </button>
            @if (showLogs()) {
              <div #logBox class="ltr mt-2 h-56 overflow-auto rounded-lg bg-neutral-950 text-neutral-200 text-xs leading-relaxed p-3 whitespace-pre-wrap">
                @for (l of logs(); track $index) { <div>{{ l }}</div> }
                @if (logs().length === 0) { <div class="text-neutral-500">…بانتظار خرج التدريب</div> }
              </div>
            }
          </div>

          @if (r.status === 'failed' && r.error) {
            <pre class="ltr bg-red-50 dark:bg-red-950/30 text-red-600 dark:text-red-400 p-3 rounded-lg text-xs max-h-40 overflow-auto whitespace-pre-wrap mt-3">{{ r.error }}</pre>
          }
          @if (r.status === 'completed') {
            <div class="flex items-center gap-2 text-emerald-600 dark:text-emerald-400 mt-3"><i class="pi pi-check-circle"></i> اكتمل التدريب وأصبح الإصدار الجديد نشطًا. راجع شجرة الإصدارات.</div>
          }
        } @else {
          <div class="flex flex-col items-center justify-center gap-2 text-neutral-500 min-h-[420px]">
            <span class="text-5xl">📈</span>
            <p>اختر تدريبًا من السجلّ أو ابدأ جلسة جديدة لمتابعة المنحنى مباشرةً.</p>
          </div>
        }
      </div>
    </div>

    <p-dialog header="معاينة بيانات التدريب" [(visible)]="showPreview" [modal]="true" [style]="{ width: '720px', maxWidth: '94vw' }" [dismissableMask]="true">
      <p class="text-neutral-500 text-sm">عيّنة من الأمثلة المبنيّة من الردود المعتمدة (آخر رسالة هي الهدف الذي يتعلّمه النموذج).</p>
      @for (ex of previewSample(); track $index) {
        <div class="flex flex-col gap-1.5 p-3 mb-2 rounded-lg border border-neutral-200 dark:border-neutral-800">
          @for (m of ex.messages; track $index) {
            <div class="flex gap-2 text-[0.82rem]" [class.border-t]="$last" [class.border-dashed]="$last" [class.border-neutral-200]="$last" [class.dark:border-neutral-700]="$last" [class.pt-1.5]="$last">
              <span class="ltr text-[0.68rem] text-blue-600 dark:text-blue-400 min-w-[70px]">{{ m.role }}</span>
              <span class="whitespace-pre-wrap">{{ m.content }}</span>
            </div>
          }
        </div>
      }
      @if (previewSample().length === 0) { <p class="text-neutral-500">لا أمثلة بعد.</p> }
    </p-dialog>
  `,
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
  readonly showAdvanced = signal(false);
  readonly previewSample = signal<any[]>([]);
  showPreview = false;

  // live terminal logs (trainer stdout/stderr streamed over the run WS)
  readonly logs = signal<string[]>([]);
  readonly showLogs = signal(true);
  @ViewChild('logBox') private logBox?: ElementRef<HTMLDivElement>;

  runName = '';
  onlyCorrected = false;
  useCorrections = true;
  hyper: { epochs: number; learning_rate: number; lora_r: number; lora_alpha: number; max_seq_len: number; grad_accum_steps: number } = {
    epochs: 3, learning_rate: 0.0002, lora_r: 16, lora_alpha: 32,
    max_seq_len: 4096, grad_accum_steps: 16,
  };

  // ── from-scratch state (kind === 'scratch') ──
  readonly families = FAMILIES;
  readonly isScratch = signal(false);
  readonly spec = signal<ArchitectureSpec | null>(null);
  readonly datasets = signal<{ repo: string; text_field: string }[]>([]);
  dsQuery = '';
  readonly dsResults = signal<any[]>([]);
  readonly dsSearching = signal(false);
  readonly estimate = signal<FeasibilityEstimate | null>(null);
  readonly estimating = signal(false);
  private projectConfig: Record<string, any> = {};   // full default_train_config (round-tripped on save)
  scratchHyper: { epochs: number; learning_rate: number; max_seq_len: number; max_train_samples: number; grad_accum_steps: number } = {
    epochs: 1, learning_rate: 0.0003, max_seq_len: 1024, max_train_samples: 5000, grad_accum_steps: 16,
  };
  readonly isMoe = computed(() => ['qwen3_moe', 'mixtral'].includes(this.spec()?.family ?? ''));
  /** Structural checks the trainer enforces; each failure blocks the run. */
  readonly archErrors = computed<string[]>(() => {
    const s = this.spec();
    if (!s) return [];
    const errs: string[] = [];
    const kv = s.num_key_value_heads || s.num_attention_heads;
    if (s.num_attention_heads && s.hidden_size % s.num_attention_heads) {
      errs.push(`hidden_size (${s.hidden_size}) غير قابل للقسمة على attn heads (${s.num_attention_heads}).`);
    }
    if (kv && s.num_attention_heads % kv) {
      errs.push(`attn heads (${s.num_attention_heads}) يجب أن يكون مضاعفًا لـ kv heads (${kv}).`);
    }
    if (this.isMoe() && s.num_experts_per_tok > s.num_experts) {
      errs.push(`experts/token (${s.num_experts_per_tok}) لا يمكن أن يتجاوز num_experts (${s.num_experts}).`);
    }
    return errs;
  });
  readonly archValid = computed(() => this.archErrors().length === 0);
  readonly canStartScratch = computed(
    () => this.isScratch() && this.datasets().length > 0 && this.archValid() && !this.starting(),
  );
  /** QLoRA needs at least one source: approved corrections or an HF dataset. */
  canStartFinetune(): boolean {
    if (this.starting()) return false;
    return (this.useCorrections && this.preview() > 0) || this.datasets().length > 0;
  }

  private socket: WebSocket | null = null;
  private steps: number[] = [];
  private losses: number[] = [];
  private estTimer: any = null;

  chartOptions = {
    responsive: true, maintainAspectRatio: false, animation: { duration: 250 },
    plugins: { legend: { labels: { color: 'rgba(120,120,120,0.85)' } } },
    scales: {
      x: { ticks: { color: 'rgba(120,120,120,0.7)' }, grid: { color: 'rgba(120,120,120,0.12)' }, title: { display: true, text: 'step', color: 'rgba(120,120,120,0.7)' } },
      y: { ticks: { color: 'rgba(120,120,120,0.7)' }, grid: { color: 'rgba(120,120,120,0.12)' }, title: { display: true, text: 'loss', color: 'rgba(120,120,120,0.7)' } },
    },
  };

  ngOnInit(): void {
    this.loadRuns();
    this.api.getProject(this.projectId).subscribe((p) => {
      const c = (p.default_train_config ?? {}) as Record<string, any>;
      this.projectConfig = c;
      if (p.kind === 'scratch') {
        this.isScratch.set(true);
        if (c['architecture']) this.spec.set({ ...(c['architecture'] as ArchitectureSpec) });
        this.datasets.set(this.readDatasets(c));
        const sh = this.scratchHyper as unknown as Record<string, number>;
        for (const k of Object.keys(sh)) if (c[k] != null) sh[k] = c[k];
        this.onArchChange();
      } else {
        this.loadPreview();
        this.datasets.set(this.readDatasets(c));
        const h = this.hyper as unknown as Record<string, number>;
        for (const k of Object.keys(h)) if (c[k] != null) h[k] = c[k];
      }
    });
  }
  ngOnDestroy(): void { this.socket?.close(); clearTimeout(this.estTimer); }

  verdictAr(v: string): string { return VERDICT_AR[v] ?? v; }
  verdictSev(v: string) { return VERDICT_SEV[v] ?? 'info'; }

  /** Read the corpus list from a config, falling back to the legacy single repo. */
  private readDatasets(c: Record<string, any>): { repo: string; text_field: string }[] {
    const list = Array.isArray(c['datasets']) ? c['datasets'] : [];
    const out = list
      .filter((d: any) => d && d.repo)
      .map((d: any) => ({ repo: d.repo, text_field: d.text_field || 'text' }));
    if (out.length) return out;
    if (c['dataset_repo']) return [{ repo: c['dataset_repo'], text_field: (c['text_field'] as string) || 'text' }];
    return [];
  }

  hasDs(repo: string): boolean { return this.datasets().some((d) => d.repo === repo); }
  removeDs(repo: string): void { this.datasets.update((l) => l.filter((d) => d.repo !== repo)); }
  addDs(repo: string): void {
    if (this.hasDs(repo)) { this.removeDs(repo); return; }   // toggle off if re-clicked
    this.datasets.update((l) => [...l, { repo, text_field: 'text' }]);
    this.api.datasetColumns(repo).subscribe({
      next: (col) => {
        const cand = (col.text_field_candidates?.length ? col.text_field_candidates : col.columns) ?? [];
        if (cand.length) {
          this.datasets.update((l) =>
            l.map((d) => (d.repo === repo && d.text_field === 'text' ? { ...d, text_field: cand[0] } : d)));
        } else {
          this.toast.add({ severity: 'warn', summary: 'تعذّر قراءة أعمدة المجموعة',
            detail: `${repo} — تأكّد من صحة المعرّف؛ قد تُتخطّى أثناء التدريب.`, life: 7000 });
        }
      },
      error: () => {},
    });
  }
  searchDs(): void {
    if (!this.dsQuery.trim()) return;
    this.dsSearching.set(true);
    this.api.searchDatasets(this.dsQuery.trim()).subscribe({
      next: (r) => { this.dsResults.set(r); this.dsSearching.set(false); },
      error: () => { this.dsSearching.set(false); this.toast.add({ severity: 'error', summary: 'تعذّر البحث' }); },
    });
  }

  /** Debounced architecture feasibility estimate (params + memory verdict). */
  onArchChange(): void {
    const cur = this.spec();
    if (!cur) return;
    // ngModel mutates the spec object in place; re-set the signal with a fresh
    // reference so the archErrors/isMoe/archValid computeds recompute.
    const s = { ...cur };
    this.spec.set(s);
    clearTimeout(this.estTimer);
    this.estimating.set(true);
    this.estTimer = setTimeout(() => {
      this.api.estimateArchitecture(s).subscribe({
        next: (e) => { this.estimate.set(e); this.estimating.set(false); },
        error: () => this.estimating.set(false),
      });
    }, 350);
  }

  /** Persist the (possibly edited) architecture + knobs, then launch a full run. */
  startScratch(): void {
    if (!this.canStartScratch()) return;
    this.starting.set(true);
    const datasets = this.datasets().map((d) => ({
      repo: d.repo, config: null, split: 'train', text_field: d.text_field || 'text',
    }));
    const first = datasets[0];
    const merged = {
      ...this.projectConfig,
      architecture: this.spec(),
      // Multi-dataset corpus; legacy single fields mirror the first for back-compat.
      datasets,
      dataset_repo: first?.repo ?? '',
      text_field: first?.text_field ?? 'text',
      epochs: this.scratchHyper.epochs,
      learning_rate: this.scratchHyper.learning_rate,
      max_seq_len: this.scratchHyper.max_seq_len,
      max_train_samples: this.scratchHyper.max_train_samples,
      grad_accum_steps: this.scratchHyper.grad_accum_steps,
    };
    this.api.updateProject(this.projectId, { default_train_config: merged }).subscribe({
      next: () => {
        this.projectConfig = merged;
        const name = this.runName.trim() || `run-${this.runs().length + 1}`;
        this.api.createRun(this.projectId, { name, autostart: true, hyperparams: {} }).subscribe({
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
      },
      error: (e) => { this.starting.set(false); this.toast.add({ severity: 'error', summary: 'تعذّر حفظ المعمارية', detail: String(e?.error?.detail ?? e.message) }); },
    });
  }

  loadPreview(): void { this.api.datasetPreview(this.projectId).subscribe((p) => this.preview.set(p.count)); }
  loadRuns(): void {
    this.api.listRuns(this.projectId).subscribe((r) => {
      this.runs.set(r);
      // Auto-attach to an in-progress run so live metrics stream immediately on
      // page load — without this you'd have to click the run, and short runs can
      // finish before you do.
      if (!this.selected()) {
        const active = r.find((x) => x.status === 'running' || x.status === 'preparing');
        if (active) this.watch(active);
      }
    });
  }

  openPreview(): void {
    this.api.datasetPreview(this.projectId).subscribe((p) => {
      this.preview.set(p.count);
      this.previewSample.set(p.sample ?? []);
      this.showPreview = true;
    });
  }

  start(): void {
    this.starting.set(true);
    const name = this.runName.trim() || `run-${this.runs().length + 1}`;
    this.api.createRun(this.projectId, {
      name, only_corrected: this.onlyCorrected, autostart: true,
      use_corrections: this.useCorrections,
      datasets: this.datasets().map((d) => ({
        repo: d.repo, config: null, split: 'train', text_field: d.text_field || 'text',
      })),
      hyperparams: { ...this.hyper },
    }).subscribe({
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
    this.logs.set([]);
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
      else if (msg.type === 'log') this.onLog(msg.data?.line ?? '');
      else if (msg.type === 'status') this.onStatus(msg.data);
    };
    sock.onerror = () => {};
  }

  /** Append a raw trainer log line (ring buffer, auto-scrolled to the bottom). */
  private onLog(line: string): void {
    if (!line) return;
    const next = [...this.logs(), line];
    if (next.length > 500) next.splice(0, next.length - 500);
    this.logs.set(next);
    queueMicrotask(() => {
      const el = this.logBox?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
    });
  }

  private onMetric(p: MetricPoint): void {
    if (p.event === 'dataset_error') {
      // A single corpus failed to load (typo / private / removed) — the run
      // continues on the rest. Surface which one so the user can fix it.
      this.toast.add({
        severity: 'warn', summary: 'تم تخطّي مجموعة بيانات',
        detail: `${(p as any).repo}: ${(p as any).error ?? ''}`,
        life: 8000,
      });
      return;
    }
    if (p.event === 'oom_retry') {
      // GPU ran out of memory → backend halved seq_len and is retrying. Reset
      // the curve so the new attempt draws cleanly.
      this.resetChart();
      this.toast.add({
        severity: 'warn', summary: 'نفاد ذاكرة GPU',
        detail: `قلّصنا طول السياق إلى ${(p as any).new_seq_len} وأعدنا المحاولة تلقائيًا.`,
        life: 6000,
      });
      return;
    }
    if (p.event === 'log' && p.step != null && p.loss != null) {
      this.steps.push(p.step);
      this.losses.push(p.loss);
      this.chartData.set({
        labels: [...this.steps],
        datasets: [{
          label: 'loss', data: [...this.losses], tension: 0.35, borderWidth: 2,
          borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.15)', fill: true, pointRadius: 0,
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

  // `||` (not `??`): a 0 estimate (HF-dataset-only run) falls through to the stream value.
  totalSteps(): number { return Number(this.selected()?.progress?.total_steps || this.live().total_steps || 0); }
  progressPct(): number {
    const total = this.totalSteps(); const step = this.live().step ?? 0;
    return total ? Math.min(100, Math.round((step / total) * 100)) : 0;
  }
  statusAr(s: RunStatus): string { return STATUS_AR[s]; }
  sev(s: RunStatus) { return STATUS_SEV[s]; }

  private resetChart(): void { this.steps = []; this.losses = []; this.chartData.set(this.emptyChart()); }
  private emptyChart() {
    return { labels: [], datasets: [{ label: 'loss', data: [], borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.15)', fill: true, tension: 0.35, pointRadius: 0 }] };
  }
}
