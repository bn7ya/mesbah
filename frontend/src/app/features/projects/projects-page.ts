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
import { ProgressBarModule } from 'primeng/progressbar';
import { MessageService } from 'primeng/api';
import { Api } from '../../core/api';
import {
  ArchitectureSpec, DatasetHit, FeasibilityEstimate, HubModel, Project,
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
    ProgressBarModule,
  ],
  template: `
    <section class="max-w-6xl mx-auto px-4 pt-2 pb-8">
      <div class="flex items-end justify-between gap-4 mb-6">
        <div>
          <h1 class="text-2xl font-semibold mb-1">المشاريع</h1>
          <p class="text-sm text-neutral-500 dark:text-neutral-400 m-0">درّب نموذجًا عبر <code class="ltr">QLoRA</code> على نموذج جاهز، أو ابنِ نموذجًا <strong>من الصفر</strong> وفق معمارية تختارها.</p>
        </div>
        <p-button label="مشروع جديد" icon="pi pi-plus" (onClick)="openNew()" />
      </div>

      @if (loading()) {
        <div class="text-center py-12 text-neutral-500 dark:text-neutral-400">…جارٍ التحميل</div>
      } @else if (projects().length === 0) {
        <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 text-center py-14 px-8">
          <span class="block text-5xl mb-3">🕯️</span>
          <h3 class="text-base font-semibold mb-1">لا توجد مشاريع بعد</h3>
          <p class="text-neutral-500 dark:text-neutral-400 mb-4">ابدأ بإنشاء مشروع: تدريب على نموذج جاهز، أو بناء نموذج من الصفر.</p>
          <p-button label="أنشئ أول مشروع" icon="pi pi-plus" (onClick)="openNew()" />
        </div>
      } @else {
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          @for (p of projects(); track p.id) {
            <a class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-4 flex flex-col gap-2 no-underline text-neutral-800 dark:text-neutral-100 transition-colors hover:border-neutral-300 dark:hover:border-neutral-700 hover:bg-neutral-50 dark:hover:bg-neutral-800/50" [routerLink]="['/projects', p.id]">
              <div class="flex justify-between items-center gap-2">
                <h3 class="text-base font-semibold m-0">{{ p.name }}</h3>
                <p-tag [value]="p.kind === 'scratch' ? 'from scratch' : 'fine-tune'"
                       [severity]="p.kind === 'scratch' ? 'warn' : 'contrast'" styleClass="lang" />
              </div>
              <code class="ltr text-xs text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40 px-2 py-0.5 rounded-md w-fit">{{ p.base_model_repo }}</code>
              @if (p.description) { <p class="text-sm text-neutral-500 dark:text-neutral-400 m-0">{{ p.description }}</p> }
              <div class="flex flex-wrap gap-3 text-xs text-neutral-500 dark:text-neutral-400">
                <span><i class="pi pi-comments"></i> {{ p.session_count }} جلسة</span>
                <span><i class="pi pi-check-square"></i> {{ p.task_count }} مهمة</span>
                <span><i class="pi pi-sitemap"></i> {{ p.version_count }} إصدار</span>
              </div>
              <div class="text-xs text-neutral-400 mt-auto pt-1">آخر تحديث {{ p.updated_at | date:'short' }}</div>
            </a>
          }
        </div>
      }
    </section>

    <p-dialog [header]="dialogHeader()" [(visible)]="dialog" [modal]="true"
              [style]="{ width: '820px', maxWidth: '95vw' }" [dismissableMask]="true">
      <div class="min-h-[280px] overflow-x-hidden">
        <!-- ── STEP 0: kind ── -->
        @if (step() === 0) {
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <button class="text-start p-5 cursor-pointer rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 flex flex-col gap-2 transition-colors hover:border-neutral-300 dark:hover:border-neutral-700" [class.ring-2]="kind() === 'finetune'" [class.ring-blue-500]="kind() === 'finetune'" type="button" (click)="kind.set('finetune')">
              <span class="text-3xl">🎯</span>
              <h4 class="text-base font-semibold m-0">تدريب نموذج جاهز <code class="ltr">fine-tune</code></h4>
              <p class="text-neutral-500 dark:text-neutral-400 text-sm m-0">اختر نموذجًا مُدرَّبًا مسبقًا من <code class="ltr">HuggingFace</code> وحسّنه عبر <code class="ltr">QLoRA</code>. مُوصى به ومجدٍ على 16GB.</p>
            </button>
            <button class="text-start p-5 cursor-pointer rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 flex flex-col gap-2 transition-colors hover:border-neutral-300 dark:hover:border-neutral-700" [class.ring-2]="kind() === 'scratch'" [class.ring-blue-500]="kind() === 'scratch'" type="button" (click)="kind.set('scratch')">
              <span class="text-3xl">🧬</span>
              <h4 class="text-base font-semibold m-0">بناء نموذج من الصفر <code class="ltr">from scratch</code></h4>
              <p class="text-neutral-500 dark:text-neutral-400 text-sm m-0">صمّم المعمارية (عدد الـ experts، نافذة السياق، الطبقات) وابدأ من أوزان عشوائية. تجريبي — يعتمد على <code class="ltr">paged training</code>.</p>
            </button>
          </div>
        }

        <!-- ── FINETUNE (single step) ── -->
        @if (step() === 1 && kind() === 'finetune') {
          <div class="flex flex-col gap-2">
            <label class="font-semibold mt-1 block">اسم المشروع</label>
            <input pInputText class="w-full" [(ngModel)]="form.name" placeholder="مثال: مساعد خدمة العملاء بالعربية" />
            <label class="font-semibold mt-1 block">الوصف <span class="text-neutral-400">(اختياري)</span></label>
            <textarea pTextarea class="w-full" rows="2" [(ngModel)]="form.description" placeholder="ماذا سيتعلم هذا النموذج؟"></textarea>
            <label class="font-semibold mt-1 block">النموذج الأساسي <code class="ltr">base model</code></label>
            <div class="flex items-center gap-2">
              <i class="pi pi-search text-neutral-400"></i>
              <input pInputText class="flex-1 min-w-0 ltr" [(ngModel)]="mQuery" (keydown.enter)="searchM()" placeholder="ابحث في HuggingFace: Qwen3, ALLaM, Arabic…" />
              <p-button label="بحث" [loading]="mSearching()" (onClick)="searchM()" size="small" />
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-1">
              @for (m of pickerModels(); track m.repo_id) {
                <button class="text-start p-3 cursor-pointer rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 flex flex-col gap-2 transition-colors hover:border-neutral-300 dark:hover:border-neutral-700" [class.ring-2]="form.base_model_repo === m.repo_id" [class.ring-blue-500]="form.base_model_repo === m.repo_id" (click)="selectCard(m.repo_id)" type="button">
                  <div class="flex justify-between items-center gap-2 min-w-0">
                    <span class="ltr font-bold text-sm truncate">{{ m.repo_id }}</span>
                    @if (m.gated) { <p-tag value="gated" severity="warn" /> }
                  </div>
                  <div class="flex flex-wrap gap-1.5 items-center">
                    @if (m.params) { <span class="text-xs px-1.5 py-0.5 rounded-md bg-neutral-100 dark:bg-neutral-800 ltr">{{ m.params }}</span> }
                    @if (m.license) { <span class="text-xs px-1.5 py-0.5 rounded-md bg-neutral-100 dark:bg-neutral-800 ltr">{{ m.license }}</span> }
                    @if (m.downloads != null) { <span class="text-xs text-neutral-400 ltr"><i class="pi pi-download"></i> {{ m.downloads }}</span> }
                    @if (m.source === 'local') { <span class="text-xs text-emerald-600 dark:text-emerald-400"><i class="pi pi-check-circle"></i> محلي</span> }
                  </div>
                </button>
              } @empty { <p class="text-neutral-400 text-sm m-0 sm:col-span-2">لا نتائج — ابحث أعلاه أو أدخل معرّفًا مخصّصًا.</p> }
            </div>
            <label class="font-semibold mt-1 block">أو معرّف نموذج مخصص من <code class="ltr">HuggingFace</code></label>
            <input pInputText class="ltr w-full" [ngModel]="customRepo()" (ngModelChange)="setCustom($event)"
                   placeholder="مثال: Qwen/Qwen3-8B" />
            @if (form.base_model_repo) {
              <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-900 p-3 flex flex-col gap-2">
                <div class="flex items-center gap-2 flex-wrap text-sm">
                  <code class="ltr text-blue-600 dark:text-blue-400">{{ form.base_model_repo }}</code>
                  @if (selInfo(); as info) {
                    <span class="text-xs text-neutral-500 dark:text-neutral-400 ltr">{{ info.model_type }}</span>
                    @if (info.max_position_embeddings) { <span class="text-xs px-1.5 py-0.5 rounded bg-neutral-100 dark:bg-neutral-800 ltr">context {{ info.max_position_embeddings }}</span> }
                    @if (info.num_hidden_layers) { <span class="text-xs px-1.5 py-0.5 rounded bg-neutral-100 dark:bg-neutral-800 ltr">{{ info.num_hidden_layers }} layers</span> }
                  } @else if (selInfoError()) {
                    <span class="text-xs text-red-500">{{ selInfoError() }}</span>
                  }
                </div>
                @if (selDl(); as st) {
                  @if (st.status === 'absent') {
                    <div class="flex items-center gap-2 text-xs text-amber-600 dark:text-amber-400">
                      <i class="pi pi-exclamation-triangle"></i> النموذج غير محمّل محليًا — سيُنزَّل عند أول استخدام، أو
                      <p-button label="تنزيل الآن" icon="pi pi-download" size="small" [text]="true" (onClick)="downloadSel()" />
                    </div>
                  } @else if (st.status === 'downloading' || st.status === 'pending') {
                    <div class="flex items-center gap-2">
                      <p-progressBar [value]="st.percent ?? 0" [showValue]="false" styleClass="w-32" [mode]="st.total_bytes ? 'determinate' : 'indeterminate'" />
                      <span class="text-xs text-neutral-400 ltr">{{ st.percent }}%</span>
                    </div>
                  } @else if (st.status === 'done') {
                    <span class="text-xs text-emerald-600 dark:text-emerald-400"><i class="pi pi-check-circle"></i> محمّل محليًا</span>
                  } @else if (st.status === 'error') {
                    <span class="text-xs text-red-500" [title]="st.error || ''"><i class="pi pi-times-circle"></i> فشل التنزيل</span>
                  }
                }
              </div>
            }
          </div>
        }

        <!-- ── SCRATCH step 1: name + architecture ── -->
        @if (step() === 1 && kind() === 'scratch') {
          <div class="flex flex-col gap-2">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div class="min-w-0">
                <label class="font-semibold mb-1 block">اسم المشروع</label>
                <input pInputText class="w-full" [(ngModel)]="form.name" placeholder="نموذجي من الصفر" />
              </div>
              <div class="min-w-0">
                <label class="font-semibold mb-1 block">العائلة <code class="ltr">family</code></label>
                <p-select [options]="families" optionLabel="label" optionValue="value"
                          [(ngModel)]="spec().family" (ngModelChange)="onArchChange()" appendTo="body" styleClass="w-full" />
              </div>
            </div>
            <div class="grid grid-cols-2 lg:grid-cols-4 gap-2 mt-1">
              <div class="min-w-0"><label class="font-semibold ltr block text-sm mb-1">layers</label><p-inputNumber [(ngModel)]="spec().num_hidden_layers" (ngModelChange)="onArchChange()" [min]="1" [max]="256" [showButtons]="true" styleClass="w-full" /></div>
              <div class="min-w-0"><label class="font-semibold ltr block text-sm mb-1">hidden_size</label><p-inputNumber [(ngModel)]="spec().hidden_size" (ngModelChange)="onArchChange()" [min]="8" [step]="64" [showButtons]="true" styleClass="w-full" /></div>
              <div class="min-w-0"><label class="font-semibold ltr block text-sm mb-1">attn heads</label><p-inputNumber [(ngModel)]="spec().num_attention_heads" (ngModelChange)="onArchChange()" [min]="1" [max]="256" [showButtons]="true" styleClass="w-full" /></div>
              <div class="min-w-0"><label class="font-semibold ltr block text-sm mb-1">kv heads</label><p-inputNumber [(ngModel)]="spec().num_key_value_heads" (ngModelChange)="onArchChange()" [min]="1" [max]="256" [showButtons]="true" styleClass="w-full" /></div>
              <div class="min-w-0"><label class="font-semibold ltr block text-sm mb-1">vocab_size</label><p-inputNumber [(ngModel)]="spec().vocab_size" (ngModelChange)="onArchChange()" [min]="1" [step]="1000" styleClass="w-full" /></div>
              <div class="min-w-0"><label class="font-semibold block text-sm mb-1">نافذة السياق <code class="ltr">context</code></label><p-inputNumber [(ngModel)]="spec().max_position_embeddings" (ngModelChange)="onArchChange()" [min]="8" [step]="512" styleClass="w-full" /></div>
              @if (isMoe()) {
                <div class="min-w-0"><label class="font-semibold ltr block text-sm mb-1">num_experts</label><p-inputNumber [(ngModel)]="spec().num_experts" (ngModelChange)="onArchChange()" [min]="1" [max]="1024" [showButtons]="true" styleClass="w-full" /></div>
                <div class="min-w-0"><label class="font-semibold ltr block text-sm mb-1">experts/token</label><p-inputNumber [(ngModel)]="spec().num_experts_per_tok" (ngModelChange)="onArchChange()" [min]="1" [max]="1024" [showButtons]="true" styleClass="w-full" /></div>
              }
            </div>

            <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-900 p-4 flex flex-col gap-2 mt-2" [class.ring-1]="estimate()?.memory?.verdict !== 'fits_vram'" [class.ring-amber-400]="estimate()?.memory?.verdict !== 'fits_vram'">
              @if (estimating()) { <span class="text-neutral-500 dark:text-neutral-400">…تقدير الحجم</span> }
              @else if (estimate(); as e) {
                <div class="flex items-center gap-3 flex-wrap">
                  <span>الحجم: <strong class="ltr">{{ e.params.total_params_human }}</strong> param</span>
                  @if (isMoe()) { <span class="text-neutral-400 ltr">active {{ e.params.active_params_human }}</span> }
                  <p-tag [value]="verdictAr(e.memory.verdict)" [severity]="verdictSev(e.memory.verdict)" />
                  <span class="text-neutral-400 ltr">offload ~{{ e.memory.host_ram_gb }}GB (RAM/NVMe) · VRAM {{ e.memory.gpu_vram_gb }}GB</span>
                </div>
                @for (w of e.warnings; track w) { <p class="text-xs text-amber-600 dark:text-amber-500 m-0">⚠ {{ w }}</p> }
              }
            </div>
          </div>
        }

        <!-- ── SCRATCH step 2: embedding ── -->
        @if (step() === 2 && kind() === 'scratch') {
          <div class="flex flex-col gap-2">
            <label class="font-semibold mt-1 block">طبقة الـ <code class="ltr">embedding</code></label>
            <div class="flex flex-col gap-2">
              <label class="flex items-center gap-2"><p-radioButton name="emb" value="new" [(ngModel)]="embMode" (ngModelChange)="onEmbModeChange()" /> <span>طبقة جديدة قابلة للتدريب <code class="ltr">new</code></span></label>
              <label class="flex items-center gap-2"><p-radioButton name="emb" value="pretrained" [(ngModel)]="embMode" (ngModelChange)="onEmbModeChange()" /> <span>تحميل <code class="ltr">embedding</code> مُدرَّب مسبقًا (تبقى قابلة للتدريب)</span></label>
            </div>
            @if (embMode === 'pretrained') {
              <div class="flex items-center gap-2">
                <i class="pi pi-search text-neutral-400"></i>
                <input pInputText class="flex-1 min-w-0 ltr" [(ngModel)]="embQuery" (keydown.enter)="searchEmb()" placeholder="ابحث عن نموذج لمصدر الـ embedding…" />
                <p-button label="بحث" [loading]="embSearching()" (onClick)="searchEmb()" />
              </div>
              @for (r of embResults(); track r.repo_id) {
                <button class="flex items-center justify-between gap-2 rounded-md border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 px-3 py-2 cursor-pointer text-start transition-colors hover:border-neutral-300 dark:hover:border-neutral-700" [class.ring-2]="embSource() === r.repo_id" [class.ring-blue-500]="embSource() === r.repo_id" type="button" (click)="pickEmbSource(r.repo_id)">
                  <span class="ltr font-bold text-sm">{{ r.repo_id }}</span>
                </button>
              }
              @if (embArch(); as a) {
                <p class="text-xs text-neutral-500 dark:text-neutral-400 m-0">
                  <code class="ltr">hidden_size={{ a.hidden_size }}</code> · <code class="ltr">vocab={{ a.vocab_size }}</code>.
                  سيُضبط hidden_size والـ tokenizer للنموذج الجديد ليطابقا المصدر.
                </p>
              }
            } @else {
              <p class="text-xs text-neutral-500 dark:text-neutral-400 m-0">سيُهيّأ الـ embedding بأوزان عشوائية ويُدرّب مع النموذج. يُستخدم <code class="ltr">tokenizer</code> قياسي افتراضيًا.</p>
            }
          </div>
        }

        <!-- ── SCRATCH step 3: corpus (one or more datasets) ── -->
        @if (step() === 3 && kind() === 'scratch') {
          <div class="flex flex-col gap-2">
            <label class="font-semibold mt-1 block">مجموعات بيانات التدريب <code class="ltr">corpora</code> من <code class="ltr">HuggingFace</code> <span class="text-neutral-400">(يمكن اختيار أكثر من واحدة)</span></label>
            <div class="flex items-center gap-2">
              <i class="pi pi-search text-neutral-400"></i>
              <input pInputText class="flex-1 min-w-0 ltr" [(ngModel)]="dsQuery" (keydown.enter)="searchDs()" placeholder="ابحث: wikitext, arabic, oscar…" />
              <p-button label="بحث" [loading]="dsSearching()" (onClick)="searchDs()" />
            </div>
            @for (r of dsResults(); track r.repo_id) {
              <button class="flex items-center justify-between gap-2 rounded-md border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 px-3 py-2 cursor-pointer text-start transition-colors hover:border-neutral-300 dark:hover:border-neutral-700" [class.ring-2]="hasDs(r.repo_id)" [class.ring-blue-500]="hasDs(r.repo_id)" type="button" (click)="addDs(r.repo_id)">
                <span class="ltr font-bold text-sm">{{ r.repo_id }}</span>
                <span class="text-neutral-400 ltr text-xs">
                  @if (r.downloads) { ↓ {{ r.downloads }} }
                  {{ hasDs(r.repo_id) ? '· مضافة ✓' : '· + إضافة' }}
                </span>
              </button>
            }
            @if (dsSelected().length) {
              <label class="font-semibold mt-1 block">المختارة <span class="text-neutral-400">({{ dsSelected().length }})</span></label>
              @for (d of dsSelected(); track d.repo) {
                <div class="flex items-center gap-2 rounded-md border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 px-3 py-2">
                  <span class="ltr flex-1 min-w-0 truncate font-bold text-sm">{{ d.repo }}</span>
                  <input pInputText class="ltr w-32 text-sm" [(ngModel)]="d.text_field" placeholder="text field" title="text field" />
                  <button class="text-red-500 hover:text-red-600 dark:hover:text-red-400 cursor-pointer inline-flex p-1" type="button" (click)="removeDs(d.repo)" title="إزالة"><i class="pi pi-times"></i></button>
                </div>
              }
            } @else {
              <p class="text-xs text-neutral-500 dark:text-neutral-400 m-0">ابحث ثم اضغط على مجموعة لإضافتها. عند اختيار عدّة مجموعات تُدمج وتُخلط قبل التدريب (حدّ <code class="ltr">max_train_samples</code> يُطبَّق على المجموع).</p>
            }
          </div>
        }

        <!-- ── SCRATCH step 4: ZeRO-Infinity offload ── -->
        @if (step() === 4 && kind() === 'scratch') {
          <div class="flex flex-col gap-2">
            <label class="flex items-center gap-2"><p-checkbox [(ngModel)]="paged" [binary]="true" /> <span>تدريب بالإزاحة <code class="ltr">ZeRO-Infinity</code> (GPU→RAM→NVMe)</span></label>
            <p class="text-xs text-neutral-500 dark:text-neutral-400 m-0">يبثّ الأوزان والـ optimizer إلى الـ RAM ثم الـ NVMe، ويبقي طبقة واحدة فقط على الـ GPU. يجعل نموذجًا أكبر من الـ VRAM <strong>يُكمل التدريب</strong> — أبطأ بكثير، لكنه ينتهي.</p>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div class="min-w-0">
                <label class="font-semibold ltr block mb-1">offload target</label>
                <p-select [options]="offloadTargets" optionLabel="label" optionValue="value" [(ngModel)]="offloadTarget" appendTo="body" styleClass="w-full" />
              </div>
              <div class="min-w-0">
                <label class="font-semibold ltr block mb-1">gpu_budget_gb: {{ gpuBudget() }}</label>
                <p-slider [(ngModel)]="gpuBudgetModel" [min]="1" [max]="vram()" [step]="1" styleClass="w-full" />
              </div>
            </div>
            @if (estimate(); as e) {
              <p class="text-xs text-neutral-500 dark:text-neutral-400 m-0">حجم الإزاحة المتوقّع: <code class="ltr">~{{ e.memory.host_ram_gb }}GB</code> (RAM ثم NVMe). الحالة: <strong>{{ verdictAr(e.memory.verdict) }}</strong>.</p>
            }
            <div class="rounded-lg border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/30 p-4 flex flex-col gap-2 mt-2">
              <p class="text-xs text-amber-600 dark:text-amber-500 m-0">⚠ الإزاحة تحلّ مشكلة الذاكرة فيكتمل التدريب — لكنها لا توفّر الحوسبة/البيانات التي يحتاجها نموذج حقيقي من الصفر. توقّع نموذجًا تجريبيًا وزمنًا طويلًا جدًا.</p>
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
})
export class ProjectsPage implements OnInit {
  private api = inject(Api);
  private router = inject(Router);
  private toast = inject(MessageService);

  readonly families = FAMILIES;
  readonly offloadTargets = OFFLOAD_TARGETS;
  offloadTarget = 'auto';
  readonly projects = signal<Project[]>([]);
  readonly models = signal<HubModel[]>([]);          // featured, live from the HF API
  readonly localRepos = signal<string[]>([]);
  readonly loading = signal(true);
  readonly dialog = signal(false);
  readonly creating = signal(false);

  // wizard
  readonly step = signal(0);
  readonly kind = signal<Kind>('finetune');
  form = { name: '', description: '', base_model_repo: '' };
  readonly customRepo = signal('');
  private defaultBaseModel = '';

  // fine-tune — model search + selected-model facts/download
  mQuery = '';
  readonly mResults = signal<HubModel[]>([]);
  readonly mSearching = signal(false);
  readonly selInfo = signal<{ model_type: string | null; max_position_embeddings: number | null; num_hidden_layers: number | null } | null>(null);
  readonly selInfoError = signal('');
  readonly selDl = signal<{ status: string; percent?: number; total_bytes?: number; error?: string | null } | null>(null);
  private selDlTimer: any = null;
  /** Search results when present, else the featured list (local models flagged). */
  readonly pickerModels = computed<HubModel[]>(() => {
    const list = this.mResults().length ? this.mResults() : this.models();
    const local = new Set(this.localRepos());
    return list.map((m) => (local.has(m.repo_id) ? { ...m, source: 'local' as const } : m));
  });

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

  // scratch — corpus (one or more datasets)
  dsQuery = '';
  readonly dsResults = signal<DatasetHit[]>([]);
  readonly dsSearching = signal(false);
  readonly dsSelected = signal<{ repo: string; text_field: string }[]>([]);

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
    if (v.trim()) { this.form.base_model_repo = v.trim(); this.onModelSelected(); }
  }
  selectCard(repo: string): void {
    this.form.base_model_repo = repo;
    this.customRepo.set('');
    this.onModelSelected();
  }

  searchM(): void {
    const q = this.mQuery.trim();
    if (!q) { this.mResults.set([]); return; }
    this.mSearching.set(true);
    this.api.searchModels(q).subscribe({
      next: (r) => { this.mResults.set(r as HubModel[]); this.mSearching.set(false); },
      error: () => this.mSearching.set(false),
    });
  }

  /** Inspect the chosen repo (context length + validation) and check its download state. */
  private onModelSelected(): void {
    const repo = this.form.base_model_repo;
    this.selInfo.set(null); this.selInfoError.set(''); this.selDl.set(null);
    clearInterval(this.selDlTimer);
    if (!repo) return;
    this.api.inspectModel(repo).subscribe({
      next: (a) => this.selInfo.set({ model_type: a.model_type, max_position_embeddings: a.max_position_embeddings, num_hidden_layers: a.num_hidden_layers }),
      error: (e) => this.selInfoError.set(String(e?.error?.detail ?? e.message)),
    });
    this.api.downloadStatus(repo).subscribe((s) => {
      if (this.form.base_model_repo === repo) this.selDl.set(s);
    });
  }

  downloadSel(): void {
    const repo = this.form.base_model_repo;
    if (!repo) return;
    this.selDl.set({ status: 'pending', percent: 0 });
    this.api.downloadModel(repo).subscribe({
      next: () => {
        clearInterval(this.selDlTimer);
        this.selDlTimer = setInterval(() => {
          this.api.downloadStatus(repo).subscribe((s) => {
            if (this.form.base_model_repo !== repo) { clearInterval(this.selDlTimer); return; }
            this.selDl.set(s);
            if (s.status === 'done' || s.status === 'error') clearInterval(this.selDlTimer);
          });
        }, 1500);
      },
      error: (e) => this.selDl.set({ status: 'error', error: String(e?.error?.detail ?? e.message) }),
    });
  }

  ngOnInit(): void {
    this.api.listProjects().subscribe({
      next: (p) => { this.projects.set(p); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
    this.api.featuredModels().subscribe((m) => this.models.set(m));
    this.api.localModels().subscribe((l) => this.localRepos.set(l.map((x: any) => x.repo_id)));
    this.api.system().subscribe((s) => {
      const v = s.gpu_vram_gb || 16;
      this.vram.set(v);
      this.gpuBudget.set(Math.max(1, v - 1));
      this.defaultBaseModel = s.default_base_model || '';
    });
  }

  /** Default pick: a locally downloaded featured model → first featured → system default. */
  private defaultRepo(): string {
    const local = new Set(this.localRepos());
    const models = this.models();
    return models.find((m) => local.has(m.repo_id))?.repo_id
      ?? models[0]?.repo_id
      ?? this.defaultBaseModel;
  }

  openNew(): void {
    this.step.set(0);
    this.kind.set('finetune');
    this.customRepo.set('');
    this.mQuery = ''; this.mResults.set([]);
    this.form = { name: '', description: '', base_model_repo: this.defaultRepo() };
    if (this.form.base_model_repo) this.onModelSelected();
    this.spec.set(freshSpec());
    this.estimate.set(null);
    this.embMode = 'new'; this.embSource.set(''); this.embArch.set(null); this.embResults.set([]); this.embQuery = '';
    this.dsSelected.set([]); this.dsResults.set([]); this.dsQuery = '';
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
    // scratch: name + at least one corpus chosen
    return !!this.form.name.trim() && this.dsSelected().length > 0;
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
  hasDs(repo: string): boolean { return this.dsSelected().some((d) => d.repo === repo); }
  removeDs(repo: string): void { this.dsSelected.update((l) => l.filter((d) => d.repo !== repo)); }
  addDs(repo: string): void {
    if (this.hasDs(repo)) { this.removeDs(repo); return; }   // toggle off if re-clicked
    this.dsSelected.update((l) => [...l, { repo, text_field: 'text' }]);
    // Suggest a real text field for this dataset (best-effort).
    this.api.datasetColumns(repo).subscribe({
      next: (c) => {
        const cand = (c.text_field_candidates?.length ? c.text_field_candidates : c.columns) ?? [];
        if (cand.length) {
          this.dsSelected.update((l) =>
            l.map((d) => (d.repo === repo && d.text_field === 'text'
              ? { ...d, text_field: cand[0] } : d)));
        } else {
          this.toast.add({ severity: 'warn', summary: 'تعذّر قراءة أعمدة المجموعة',
            detail: `${repo} — تأكّد من صحة المعرّف.`, life: 7000 });
        }
      },
      error: () => {},
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
    const datasets = this.dsSelected().map((d) => ({
      repo: d.repo, config: null, split: 'train', text_field: d.text_field || 'text',
    }));
    const first = datasets[0];
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
        // Multi-dataset corpus; legacy single fields mirror the first for back-compat.
        datasets,
        dataset_repo: first?.repo ?? '',
        dataset_split: 'train',
        text_field: first?.text_field ?? 'text',
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
