import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { DialogModule } from 'primeng/dialog';
import { InputTextModule } from 'primeng/inputtext';
import { TextareaModule } from 'primeng/textarea';
import { TagModule } from 'primeng/tag';
import { SelectModule } from 'primeng/select';
import { InputNumberModule } from 'primeng/inputnumber';
import { SliderModule } from 'primeng/slider';
import { CheckboxModule } from 'primeng/checkbox';
import { RadioButtonModule } from 'primeng/radiobutton';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { MessageService } from 'primeng/api';
import { Api } from '../../core/api';
import {
  ArchitectureSpec, CuratedModel, DatasetHit, FeasibilityEstimate, Project,
} from '../../core/types';

type Kind = 'finetune' | 'scratch';

const FAMILIES = [
  { label: 'Qwen3 (dense)', value: 'qwen3' },
  { label: 'Llama (dense)', value: 'llama' },
  { label: 'Mistral (dense)', value: 'mistral' },
  { label: 'Qwen3-MoE (experts)', value: 'qwen3_moe' },
  { label: 'Mixtral (experts)', value: 'mixtral' },
];

const OFFLOAD_TARGETS = [
  { label: 'auto (RAM، ثم NVMe للضخم)', value: 'auto' },
  { label: 'cpu (RAM فقط — أسرع)', value: 'cpu' },
  { label: 'nvme (قرص — للأكبر من RAM)', value: 'nvme' },
];

function freshSpec(): ArchitectureSpec {
  return {
    family: 'qwen3', num_hidden_layers: 12, hidden_size: 768,
    num_attention_heads: 12, num_key_value_heads: 4, intermediate_size: null,
    vocab_size: 32000, max_position_embeddings: 2048, tie_word_embeddings: true,
    num_experts: 8, num_experts_per_tok: 2, moe_intermediate_size: null,
  };
}

@Component({
  selector: 'app-projects-page',
  imports: [
    DatePipe, FormsModule, RouterLink, ButtonModule, DialogModule,
    InputTextModule, TextareaModule, TagModule, SelectModule, InputNumberModule,
    SliderModule, CheckboxModule, RadioButtonModule, ProgressSpinnerModule,
  ],
  template: `
    <section class="page">
      <div class="head">
        <div>
          <h1 class="title">المشاريع</h1>
          <p class="muted sub">درّب نموذجًا عبر <code class="ltr">QLoRA</code> على نموذج جاهز، أو ابنِ نموذجًا <strong>من الصفر</strong> وفق معمارية تختارها.</p>
        </div>
        <p-button label="مشروع جديد" icon="pi pi-plus" (onClick)="openNew()" />
      </div>

      @if (loading()) {
        <div class="muted center">…جارٍ التحميل</div>
      } @else if (projects().length === 0) {
        <div class="empty glass">
          <span class="big">🕯️</span>
          <h3>لا توجد مشاريع بعد</h3>
          <p class="muted">ابدأ بإنشاء مشروع: تدريب على نموذج جاهز، أو بناء نموذج من الصفر.</p>
          <p-button label="أنشئ أول مشروع" icon="pi pi-plus" (onClick)="openNew()" />
        </div>
      } @else {
        <div class="grid">
          @for (p of projects(); track p.id) {
            <a class="card glass" [routerLink]="['/projects', p.id]">
              <div class="card-top">
                <h3 class="name">{{ p.name }}</h3>
                <p-tag [value]="p.kind === 'scratch' ? 'from scratch' : 'fine-tune'"
                       [severity]="p.kind === 'scratch' ? 'warn' : 'contrast'" styleClass="lang" />
              </div>
              <code class="ltr base">{{ p.base_model_repo }}</code>
              @if (p.description) { <p class="muted desc">{{ p.description }}</p> }
              <div class="stats">
                <span><i class="pi pi-comments"></i> {{ p.session_count }} جلسة</span>
                <span><i class="pi pi-check-square"></i> {{ p.task_count }} مهمة</span>
                <span><i class="pi pi-sitemap"></i> {{ p.version_count }} إصدار</span>
              </div>
              <div class="foot muted dim">آخر تحديث {{ p.updated_at | date:'short' }}</div>
            </a>
          }
        </div>
      }
    </section>

    <p-dialog [header]="dialogHeader()" [(visible)]="dialog" [modal]="true"
              [style]="{ width: '820px', maxWidth: '95vw' }" [dismissableMask]="true">
      <div class="wiz">
        <!-- ── STEP 0: kind ── -->
        @if (step() === 0) {
          <div class="kinds">
            <button class="kind glass" [class.sel]="kind() === 'finetune'" type="button" (click)="kind.set('finetune')">
              <span class="ki">🎯</span>
              <h4>تدريب نموذج جاهز <code class="ltr">fine-tune</code></h4>
              <p class="muted">اختر نموذجًا مُدرَّبًا مسبقًا من <code class="ltr">HuggingFace</code> وحسّنه عبر <code class="ltr">QLoRA</code>. مُوصى به ومجدٍ على 16GB.</p>
            </button>
            <button class="kind glass" [class.sel]="kind() === 'scratch'" type="button" (click)="kind.set('scratch')">
              <span class="ki">🧬</span>
              <h4>بناء نموذج من الصفر <code class="ltr">from scratch</code></h4>
              <p class="muted">صمّم المعمارية (عدد الـ experts، نافذة السياق، الطبقات) وابدأ من أوزان عشوائية. تجريبي — يعتمد على <code class="ltr">paged training</code>.</p>
            </button>
          </div>
        }

        <!-- ── FINETUNE (single step) ── -->
        @if (step() === 1 && kind() === 'finetune') {
          <div class="form">
            <label class="lbl">اسم المشروع</label>
            <input pInputText [(ngModel)]="form.name" placeholder="مثال: مساعد خدمة العملاء بالعربية" />
            <label class="lbl">الوصف <span class="dim">(اختياري)</span></label>
            <textarea pTextarea rows="2" [(ngModel)]="form.description" placeholder="ماذا سيتعلم هذا النموذج؟"></textarea>
            <label class="lbl">النموذج الأساسي <code class="ltr">base model</code></label>
            <div class="models">
              @for (m of models(); track m.repo_id) {
                <button class="model glass" [class.sel]="form.base_model_repo === m.repo_id" (click)="selectCard(m.repo_id)" type="button">
                  <div class="model-head">
                    <span class="ltr repo">{{ m.label }}</span>
                    @if (m.recommended) { <p-tag value="موصى به" severity="success" /> }
                  </div>
                  <div class="badges">
                    <span class="b">{{ m.params }}</span>
                    <span class="b ltr">{{ m.context }}</span>
                    <span class="b">عربي: {{ m.arabic }}</span>
                    <span class="b ltr">{{ m.license }}</span>
                  </div>
                  <p class="muted note">{{ m.note }}</p>
                </button>
              }
            </div>
            <label class="lbl">أو معرّف نموذج مخصص من <code class="ltr">HuggingFace</code></label>
            <input pInputText class="ltr" [ngModel]="customRepo()" (ngModelChange)="setCustom($event)"
                   placeholder="مثال: Qwen/Qwen3-8B" />
          </div>
        }

        <!-- ── SCRATCH step 1: name + architecture ── -->
        @if (step() === 1 && kind() === 'scratch') {
          <div class="form">
            <div class="row2">
              <div>
                <label class="lbl">اسم المشروع</label>
                <input pInputText [(ngModel)]="form.name" placeholder="نموذجي من الصفر" />
              </div>
              <div>
                <label class="lbl">العائلة <code class="ltr">family</code></label>
                <p-select [options]="families" optionLabel="label" optionValue="value"
                          [(ngModel)]="spec().family" (ngModelChange)="onArchChange()" appendTo="body" styleClass="w-full" />
              </div>
            </div>
            <div class="grid4">
              <div><label class="lbl ltr">layers</label><p-inputNumber [(ngModel)]="spec().num_hidden_layers" (ngModelChange)="onArchChange()" [min]="1" [max]="256" [showButtons]="true" /></div>
              <div><label class="lbl ltr">hidden_size</label><p-inputNumber [(ngModel)]="spec().hidden_size" (ngModelChange)="onArchChange()" [min]="8" [step]="64" [showButtons]="true" /></div>
              <div><label class="lbl ltr">attn heads</label><p-inputNumber [(ngModel)]="spec().num_attention_heads" (ngModelChange)="onArchChange()" [min]="1" [max]="256" [showButtons]="true" /></div>
              <div><label class="lbl ltr">kv heads</label><p-inputNumber [(ngModel)]="spec().num_key_value_heads" (ngModelChange)="onArchChange()" [min]="1" [max]="256" [showButtons]="true" /></div>
              <div><label class="lbl ltr">vocab_size</label><p-inputNumber [(ngModel)]="spec().vocab_size" (ngModelChange)="onArchChange()" [min]="1" [step]="1000" /></div>
              <div><label class="lbl">نافذة السياق <code class="ltr">context</code></label><p-inputNumber [(ngModel)]="spec().max_position_embeddings" (ngModelChange)="onArchChange()" [min]="8" [step]="512" /></div>
              @if (isMoe()) {
                <div><label class="lbl ltr">num_experts</label><p-inputNumber [(ngModel)]="spec().num_experts" (ngModelChange)="onArchChange()" [min]="1" [max]="1024" [showButtons]="true" /></div>
                <div><label class="lbl ltr">experts/token</label><p-inputNumber [(ngModel)]="spec().num_experts_per_tok" (ngModelChange)="onArchChange()" [min]="1" [max]="1024" [showButtons]="true" /></div>
              }
            </div>

            <div class="est glass" [class.warn]="estimate()?.memory?.verdict !== 'fits_vram'">
              @if (estimating()) { <span class="muted">…تقدير الحجم</span> }
              @else if (estimate(); as e) {
                <div class="est-row">
                  <span>الحجم: <strong class="ltr">{{ e.params.total_params_human }}</strong> param</span>
                  @if (isMoe()) { <span class="dim ltr">active {{ e.params.active_params_human }}</span> }
                  <p-tag [value]="verdictAr(e.memory.verdict)" [severity]="verdictSev(e.memory.verdict)" />
                  <span class="dim ltr">offload ~{{ e.memory.host_ram_gb }}GB (RAM/NVMe) · VRAM {{ e.memory.gpu_vram_gb }}GB</span>
                </div>
                @for (w of e.warnings; track w) { <p class="warn-line">⚠ {{ w }}</p> }
              }
            </div>
          </div>
        }

        <!-- ── SCRATCH step 2: embedding ── -->
        @if (step() === 2 && kind() === 'scratch') {
          <div class="form">
            <label class="lbl">طبقة الـ <code class="ltr">embedding</code></label>
            <div class="radios">
              <label class="radio"><p-radioButton name="emb" value="new" [(ngModel)]="embMode" (ngModelChange)="onEmbModeChange()" /> <span>طبقة جديدة قابلة للتدريب <code class="ltr">new</code></span></label>
              <label class="radio"><p-radioButton name="emb" value="pretrained" [(ngModel)]="embMode" (ngModelChange)="onEmbModeChange()" /> <span>تحميل <code class="ltr">embedding</code> مُدرَّب مسبقًا (تبقى قابلة للتدريب)</span></label>
            </div>
            @if (embMode === 'pretrained') {
              <div class="search glass">
                <i class="pi pi-search"></i>
                <input pInputText class="grow ltr" [(ngModel)]="embQuery" (keydown.enter)="searchEmb()" placeholder="ابحث عن نموذج لمصدر الـ embedding…" />
                <p-button label="بحث" [loading]="embSearching()" (onClick)="searchEmb()" />
              </div>
              @for (r of embResults(); track r.repo_id) {
                <button class="hit glass" [class.sel]="embSource() === r.repo_id" type="button" (click)="pickEmbSource(r.repo_id)">
                  <span class="ltr repo">{{ r.repo_id }}</span>
                </button>
              }
              @if (embArch(); as a) {
                <p class="muted small">
                  <code class="ltr">hidden_size={{ a.hidden_size }}</code> · <code class="ltr">vocab={{ a.vocab_size }}</code>.
                  سيُضبط hidden_size والـ tokenizer للنموذج الجديد ليطابقا المصدر.
                </p>
              }
            } @else {
              <p class="muted small">سيُهيّأ الـ embedding بأوزان عشوائية ويُدرّب مع النموذج. يُستخدم <code class="ltr">tokenizer</code> قياسي افتراضيًا.</p>
            }
          </div>
        }

        <!-- ── SCRATCH step 3: corpus ── -->
        @if (step() === 3 && kind() === 'scratch') {
          <div class="form">
            <label class="lbl">مجموعة بيانات التدريب <code class="ltr">corpus</code> من <code class="ltr">HuggingFace</code></label>
            <div class="search glass">
              <i class="pi pi-search"></i>
              <input pInputText class="grow ltr" [(ngModel)]="dsQuery" (keydown.enter)="searchDs()" placeholder="ابحث: wikitext, arabic, oscar…" />
              <p-button label="بحث" [loading]="dsSearching()" (onClick)="searchDs()" />
            </div>
            @for (r of dsResults(); track r.repo_id) {
              <button class="hit glass" [class.sel]="dsRepo() === r.repo_id" type="button" (click)="pickDs(r.repo_id)">
                <span class="ltr repo">{{ r.repo_id }}</span>
                @if (r.downloads) { <span class="dim ltr small">↓ {{ r.downloads }}</span> }
              </button>
            }
            @if (dsRepo()) {
              <label class="lbl ltr">text field</label>
              <p-select [options]="dsColumns()" [(ngModel)]="textField" [editable]="true" appendTo="body" styleClass="w-full" placeholder="text" />
            }
          </div>
        }

        <!-- ── SCRATCH step 4: ZeRO-Infinity offload ── -->
        @if (step() === 4 && kind() === 'scratch') {
          <div class="form">
            <label class="radio"><p-checkbox [(ngModel)]="paged" [binary]="true" /> <span>تدريب بالإزاحة <code class="ltr">ZeRO-Infinity</code> (GPU→RAM→NVMe)</span></label>
            <p class="muted small">يبثّ الأوزان والـ optimizer إلى الـ RAM ثم الـ NVMe، ويبقي طبقة واحدة فقط على الـ GPU. يجعل نموذجًا أكبر من الـ VRAM <strong>يُكمل التدريب</strong> — أبطأ بكثير، لكنه ينتهي.</p>
            <div class="row2">
              <div>
                <label class="lbl ltr">offload target</label>
                <p-select [options]="offloadTargets" optionLabel="label" optionValue="value" [(ngModel)]="offloadTarget" appendTo="body" styleClass="w-full" />
              </div>
              <div>
                <label class="lbl ltr">gpu_budget_gb: {{ gpuBudget() }}</label>
                <p-slider [(ngModel)]="gpuBudgetModel" [min]="1" [max]="vram()" [step]="1" styleClass="w-full" />
              </div>
            </div>
            @if (estimate(); as e) {
              <p class="muted small">حجم الإزاحة المتوقّع: <code class="ltr">~{{ e.memory.host_ram_gb }}GB</code> (RAM ثم NVMe). الحالة: <strong>{{ verdictAr(e.memory.verdict) }}</strong>.</p>
            }
            <div class="est glass warn">
              <p class="warn-line">⚠ الإزاحة تحلّ مشكلة الذاكرة فيكتمل التدريب — لكنها لا توفّر الحوسبة/البيانات التي يحتاجها نموذج حقيقي من الصفر. توقّع نموذجًا تجريبيًا وزمنًا طويلًا جدًا.</p>
            </div>
          </div>
        }
      </div>

      <ng-template pTemplate="footer">
        <p-button label="رجوع" severity="secondary" [text]="true" [disabled]="step() === 0" (onClick)="back()" />
        @if (!isLastStep()) {
          <p-button label="التالي" icon="pi pi-arrow-left" [disabled]="!canNext()" (onClick)="next()" />
        } @else {
          <p-button label="إنشاء المشروع" icon="pi pi-check" [disabled]="!canCreate()" [loading]="creating()" (onClick)="create()" />
        }
      </ng-template>
    </p-dialog>
  `,
  styles: [`
    .page { max-width: 1180px; margin: 0 auto; padding: 0.5rem 0.6rem; }
    .head { display: flex; align-items: flex-end; justify-content: space-between; margin-bottom: 1.4rem; }
    .title { font-size: 2rem; margin: 0 0 0.2rem; }
    .sub { margin: 0; font-size: 0.9rem; }
    .center { text-align: center; padding: 3rem; }
    .empty { text-align: center; padding: 3.5rem 2rem; border-radius: var(--radius-lg); }
    .empty .big { font-size: 3rem; display: block; margin-bottom: 0.6rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 1.1rem; }
    .card { padding: 1.2rem; text-decoration: none; color: var(--text-1); display: flex; flex-direction: column; gap: 0.55rem; transition: transform 0.18s ease, box-shadow 0.18s ease; }
    .card:hover { transform: translateY(-3px); box-shadow: 0 14px 50px rgba(0,0,0,0.5); }
    .card-top { display: flex; justify-content: space-between; align-items: center; }
    .card .name { margin: 0; font-size: 1.15rem; }
    .card .base { font-size: 0.78rem; color: var(--accent); background: var(--accent-soft); padding: 0.2rem 0.5rem; border-radius: 8px; width: fit-content; }
    .card .desc { font-size: 0.85rem; margin: 0; }
    .stats { display: flex; gap: 0.9rem; font-size: 0.8rem; color: var(--text-2); flex-wrap: wrap; }
    .foot { font-size: 0.72rem; margin-top: auto; }

    .wiz { min-height: 280px; }
    .form { display: flex; flex-direction: column; gap: 0.55rem; }
    .lbl { font-weight: 600; margin-top: 0.4rem; display: block; }
    .row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0.7rem; }
    .grid4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.6rem; margin-top: 0.4rem; }
    .grid4 :is(p-inputnumber, p-select) { width: 100%; }
    .kinds { display: grid; grid-template-columns: 1fr 1fr; gap: 0.9rem; }
    .kind { text-align: start; padding: 1.2rem; cursor: pointer; border: 1px solid var(--glass-border); display: flex; flex-direction: column; gap: 0.4rem; transition: all 0.15s ease; }
    .kind:hover { border-color: var(--accent); }
    .kind.sel { border-color: var(--accent); box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 40%, transparent); }
    .kind .ki { font-size: 1.8rem; }
    .kind h4 { margin: 0; }
    .models { display: grid; grid-template-columns: 1fr 1fr; gap: 0.7rem; margin-top: 0.3rem; }
    .model { text-align: start; padding: 0.85rem; cursor: pointer; border: 1px solid var(--glass-border); display: flex; flex-direction: column; gap: 0.4rem; transition: all 0.15s ease; }
    .model:hover { border-color: var(--accent); }
    .model.sel { border-color: var(--accent); box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 40%, transparent); }
    .model-head { display: flex; justify-content: space-between; align-items: center; }
    .model .repo, .hit .repo { font-weight: 700; font-size: 0.86rem; }
    .badges { display: flex; flex-wrap: wrap; gap: 0.3rem; }
    .badges .b { font-size: 0.68rem; padding: 0.12rem 0.45rem; border-radius: 6px; background: rgba(150,95,70,0.09); }
    .model .note { font-size: 0.74rem; margin: 0; }
    .search { display: flex; align-items: center; gap: 0.5rem; padding: 0.4rem 0.6rem; }
    .search .grow { flex: 1; border: none; background: transparent; }
    .hit { display: flex; align-items: center; justify-content: space-between; gap: 0.6rem; padding: 0.55rem 0.7rem; cursor: pointer; border: 1px solid var(--glass-border); }
    .hit:hover { border-color: var(--accent); }
    .hit.sel { border-color: var(--accent); box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 40%, transparent); }
    .radios { display: flex; flex-direction: column; gap: 0.5rem; }
    .radio { display: flex; align-items: center; gap: 0.5rem; }
    .small { font-size: 0.78rem; }
    .est { padding: 0.7rem 0.85rem; display: flex; flex-direction: column; gap: 0.35rem; margin-top: 0.5rem; }
    .est.warn { border: 1px solid color-mix(in srgb, var(--warn) 45%, transparent); }
    .est-row { display: flex; align-items: center; gap: 0.7rem; flex-wrap: wrap; }
    .warn-line { font-size: 0.78rem; margin: 0; color: var(--warn); }
    .w-full { width: 100%; }
    @media (max-width: 640px) { .models, .kinds, .row2 { grid-template-columns: 1fr; } .grid4 { grid-template-columns: 1fr 1fr; } }
  `],
})
export class ProjectsPage implements OnInit {
  private api = inject(Api);
  private router = inject(Router);
  private toast = inject(MessageService);

  readonly families = FAMILIES;
  readonly offloadTargets = OFFLOAD_TARGETS;
  offloadTarget = 'auto';
  readonly projects = signal<Project[]>([]);
  readonly models = signal<CuratedModel[]>([]);
  readonly loading = signal(true);
  readonly dialog = signal(false);
  readonly creating = signal(false);

  // wizard
  readonly step = signal(0);
  readonly kind = signal<Kind>('finetune');
  form = { name: '', description: '', base_model_repo: '' };
  readonly customRepo = signal('');

  // scratch — architecture
  readonly spec = signal<ArchitectureSpec>(freshSpec());
  readonly estimate = signal<FeasibilityEstimate | null>(null);
  readonly estimating = signal(false);
  readonly isMoe = computed(() => ['qwen3_moe', 'mixtral'].includes(this.spec().family));

  // scratch — embedding
  embMode: 'new' | 'pretrained' = 'new';
  embQuery = '';
  readonly embResults = signal<DatasetHit[]>([]);
  readonly embSearching = signal(false);
  readonly embSource = signal('');
  readonly embArch = signal<{ hidden_size: number | null; vocab_size: number | null } | null>(null);

  // scratch — corpus
  dsQuery = '';
  readonly dsResults = signal<DatasetHit[]>([]);
  readonly dsSearching = signal(false);
  readonly dsRepo = signal('');
  readonly dsColumns = signal<string[]>([]);
  textField = 'text';

  // scratch — gpu
  paged = true;
  readonly gpuBudget = signal(7);
  cpuOffload = 96;
  readonly vram = signal(16);

  // p-slider needs a plain getter/setter bound to the signal
  get gpuBudgetModel(): number { return this.gpuBudget(); }
  set gpuBudgetModel(v: number) { this.gpuBudget.set(v); }

  dialogHeader(): string {
    if (this.step() === 0) return 'مشروع جديد';
    return this.kind() === 'scratch' ? 'بناء نموذج من الصفر' : 'تدريب نموذج جاهز';
  }

  setCustom(v: string): void {
    this.customRepo.set(v);
    if (v.trim()) this.form.base_model_repo = v.trim();
  }
  selectCard(repo: string): void { this.form.base_model_repo = repo; this.customRepo.set(''); }

  ngOnInit(): void {
    this.api.listProjects().subscribe({
      next: (p) => { this.projects.set(p); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
    this.api.curatedModels().subscribe((m) => this.models.set(m));
    this.api.system().subscribe((s) => {
      const v = s.gpu_vram_gb || 16;
      this.vram.set(v);
      this.gpuBudget.set(Math.max(1, v - 1));
    });
  }

  openNew(): void {
    this.step.set(0);
    this.kind.set('finetune');
    this.customRepo.set('');
    this.form = { name: '', description: '', base_model_repo: this.models().find((m) => m.recommended)?.repo_id ?? '' };
    this.spec.set(freshSpec());
    this.estimate.set(null);
    this.embMode = 'new'; this.embSource.set(''); this.embArch.set(null); this.embResults.set([]); this.embQuery = '';
    this.dsRepo.set(''); this.dsResults.set([]); this.dsColumns.set([]); this.dsQuery = ''; this.textField = 'text';
    this.paged = true; this.cpuOffload = 96; this.offloadTarget = 'auto';
    this.dialog.set(true);
  }

  // ── step navigation ──
  lastStep(): number { return this.kind() === 'scratch' ? 4 : 1; }
  isLastStep(): boolean { return this.step() === this.lastStep(); }

  next(): void {
    if (this.step() === 0 && this.kind() === 'scratch') this.onArchChange();
    this.step.update((s) => s + 1);
  }
  back(): void { this.step.update((s) => Math.max(0, s - 1)); }

  canNext(): boolean {
    if (this.step() === 0) return true;                       // a kind is always selected
    if (this.kind() === 'scratch' && this.step() === 1) return !!this.form.name.trim();
    return true;
  }

  canCreate(): boolean {
    if (!this.form.name.trim() && this.kind() === 'finetune') return false;
    if (this.kind() === 'finetune') return !!this.form.base_model_repo;
    // scratch: name + a corpus chosen
    return !!this.form.name.trim() && !!this.dsRepo();
  }

  // ── architecture estimate ──
  onArchChange(): void {
    this.estimating.set(true);
    this.api.estimateArchitecture(this.spec()).subscribe({
      next: (e) => { this.estimate.set(e); this.estimating.set(false); },
      error: () => this.estimating.set(false),
    });
  }
  verdictAr(v: string): string {
    return v === 'fits_vram' ? 'يناسب VRAM'
      : v === 'cpu_offload' ? 'إزاحة إلى RAM (سينتهي)'
      : v === 'nvme_offload' ? 'إزاحة إلى NVMe (بطيء، سينتهي)'
      : 'ضخم جدًا (حتى مع القرص)';
  }
  verdictSev(v: string): 'success' | 'warn' | 'danger' {
    return v === 'fits_vram' ? 'success' : v === 'exceeds_disk' ? 'danger' : 'warn';
  }

  // ── embedding ──
  onEmbModeChange(): void { if (this.embMode === 'new') { this.embSource.set(''); this.embArch.set(null); } }
  searchEmb(): void {
    if (!this.embQuery.trim()) return;
    this.embSearching.set(true);
    this.api.searchModels(this.embQuery.trim()).subscribe({
      next: (r) => { this.embResults.set(r as DatasetHit[]); this.embSearching.set(false); },
      error: () => this.embSearching.set(false),
    });
  }
  pickEmbSource(repo: string): void {
    this.embSource.set(repo);
    this.api.inspectModel(repo).subscribe({
      next: (a) => {
        this.embArch.set({ hidden_size: a.hidden_size, vocab_size: a.vocab_size });
        // adopt source dims so embedding load succeeds
        if (a.hidden_size) this.spec.update((s) => ({ ...s, hidden_size: a.hidden_size! }));
        if (a.vocab_size) this.spec.update((s) => ({ ...s, vocab_size: a.vocab_size! }));
      },
      error: (e) => this.toast.add({ severity: 'warn', summary: 'تعذّر فحص النموذج', detail: String(e?.error?.detail ?? e.message) }),
    });
  }

  // ── corpus ──
  searchDs(): void {
    if (!this.dsQuery.trim()) return;
    this.dsSearching.set(true);
    this.api.searchDatasets(this.dsQuery.trim()).subscribe({
      next: (r) => { this.dsResults.set(r); this.dsSearching.set(false); },
      error: () => this.dsSearching.set(false),
    });
  }
  pickDs(repo: string): void {
    this.dsRepo.set(repo);
    this.api.datasetColumns(repo).subscribe({
      next: (c) => {
        this.dsColumns.set(c.text_field_candidates?.length ? c.text_field_candidates : c.columns);
        if (this.dsColumns().length) this.textField = this.dsColumns()[0];
      },
      error: () => this.dsColumns.set([]),
    });
  }

  // ── create ──
  create(): void {
    if (!this.canCreate()) return;
    this.creating.set(true);
    const body = this.kind() === 'scratch' ? this.scratchBody() : { ...this.form };
    this.api.createProject(body).subscribe({
      next: (p) => {
        this.creating.set(false);
        this.dialog.set(false);
        this.toast.add({ severity: 'success', summary: 'تم إنشاء المشروع', detail: p.name });
        this.router.navigate(['/projects', p.id]);
      },
      error: (e) => {
        this.creating.set(false);
        this.toast.add({ severity: 'error', summary: 'تعذر الإنشاء', detail: String(e?.error?.detail ?? e.message) });
      },
    });
  }

  private scratchBody() {
    const spec = this.spec();
    return {
      name: this.form.name,
      description: this.form.description,
      kind: 'scratch',
      base_model_repo: `scratch/${spec.family}`,
      architecture: spec,
      default_train_config: {
        architecture: spec,
        embedding_mode: this.embMode,
        embedding_source_repo: this.embMode === 'pretrained' ? this.embSource() : null,
        dataset_repo: this.dsRepo(),
        dataset_split: 'train',
        text_field: this.textField || 'text',
        max_seq_len: Math.min(spec.max_position_embeddings, 1024),
        paged_training: this.paged,
        offload_target: this.offloadTarget,
        gpu_budget_gb: this.gpuBudget(),
        cpu_offload_gb: this.cpuOffload,
        epochs: 1,
        max_train_samples: 5000,
      },
    };
  }
}
