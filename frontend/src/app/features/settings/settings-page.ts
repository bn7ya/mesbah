import { Component, OnInit, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { TagModule } from 'primeng/tag';
import { MessageService } from 'primeng/api';
import { Api } from '../../core/api';
import { AppSettings, GpuInfo, SystemInfo } from '../../core/types';

type Theme = 'light' | 'dark';
const THEME_KEY = 'misbah-theme';

@Component({
  selector: 'app-settings-page',
  imports: [DecimalPipe, FormsModule, ButtonModule, InputTextModule, TagModule],
  template: `
    <section class="max-w-3xl mx-auto px-4 py-2">
      <div class="mb-6">
        <h1 class="text-2xl font-semibold m-0 mb-1">الإعدادات <code class="ltr">settings</code></h1>
        <p class="text-neutral-500 text-sm m-0">العتاد، الرموز (API tokens)، والمظهر — كلها محفوظة محليًا على جهازك.</p>
      </div>

      <!-- ── Hardware ── -->
      <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-5 mb-5">
        <h2 class="text-base font-semibold m-0 mb-1">العتاد <code class="ltr">hardware</code></h2>
        <p class="text-neutral-500 text-sm mb-4">يُكتشف تلقائيًا من جهازك. تُحسب إعدادات التدريب (طول السياق، حجم الدفعة، الإزاحة) من <code class="ltr">VRAM</code> و<code class="ltr">RAM</code> المكتشفة.</p>

        @if (sys(); as s) {
          <div class="flex flex-wrap gap-3 mb-4 text-sm">
            <span class="px-2.5 py-1 rounded-lg bg-neutral-100 dark:bg-neutral-800"><span class="text-neutral-500">RAM</span> <span class="ltr font-semibold">{{ s.system_ram_gb | number:'1.0-1' }} GB</span></span>
            <span class="px-2.5 py-1 rounded-lg bg-neutral-100 dark:bg-neutral-800"><span class="text-neutral-500">VRAM</span> <span class="ltr font-semibold">{{ s.gpu_vram_gb | number:'1.0-1' }} GB</span></span>
            <span class="px-2.5 py-1 rounded-lg bg-neutral-100 dark:bg-neutral-800"><span class="text-neutral-500">max_seq_len</span> <span class="ltr font-semibold">{{ s.max_train_seq_len }}</span></span>
          </div>

          @if (s.gpus.length) {
            <p class="text-xs font-semibold uppercase tracking-wide text-neutral-500 mb-2">اختر بطاقة/بطاقات الرسوميات للتدريب <span class="normal-case text-neutral-400">(يمكن اختيار أكثر من واحدة — يُجمع الـ VRAM)</span></p>
            <div class="flex flex-col gap-2">
              @for (g of s.gpus; track g.index) {
                <button type="button" (click)="toggleGpu(g.index)"
                  class="flex items-center justify-between gap-3 px-3.5 py-3 rounded-lg border text-start transition-colors"
                  [class]="isSelected(g) ? 'border-blue-400 dark:border-blue-500 ring-1 ring-blue-400/40 bg-blue-50/50 dark:bg-blue-950/20' : 'border-neutral-200 dark:border-neutral-800 hover:border-neutral-300 dark:hover:border-neutral-700'">
                  <div class="min-w-0">
                    <div class="font-semibold ltr truncate">{{ g.name }}</div>
                    <div class="text-xs text-neutral-400 ltr">GPU {{ g.index }} · {{ g.total_vram_gb | number:'1.0-1' }} GB
                      @if (g.compute_capability) { · sm {{ g.compute_capability }} }
                    </div>
                  </div>
                  @if (isSelected(g)) { <p-tag value="مُختارة" severity="success" icon="pi pi-check" /> }
                  @else { <span class="text-xs text-blue-600 dark:text-blue-400 shrink-0">تحديد</span> }
                </button>
              }
              @if ((s.selected_gpus.length || 0) > 1) {
                <p class="text-xs text-neutral-500 m-0"><i class="pi pi-info-circle"></i> {{ s.selected_gpus.length }}× GPU — إجمالي <span class="ltr font-semibold">{{ s.gpu_vram_gb | number:'1.0-1' }} GB</span> VRAM. التدريب يوزّع الطبقات عبر البطاقات (<code class="ltr">device_map</code>)؛ يستخدم مسار <code class="ltr">transformers</code> بدل <code class="ltr">Unsloth</code>.</p>
              }
            </div>
          } @else {
            <div class="px-3.5 py-3 rounded-lg border border-amber-300 dark:border-amber-900 bg-amber-50/60 dark:bg-amber-950/20 text-amber-700 dark:text-amber-400 text-sm">
              <i class="pi pi-exclamation-triangle"></i> لم يُكتشف <code class="ltr">GPU</code> متوافق مع <code class="ltr">CUDA</code>. سيعمل التطبيق على <code class="ltr">CPU</code> فقط (لا تدريب/استدلال حقيقي).
            </div>
          }
        } @else {
          <p class="text-neutral-400 text-sm">…جارٍ قراءة العتاد</p>
        }
      </div>

      <!-- ── HuggingFace token ── -->
      <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-5 mb-5">
        <div class="flex items-center justify-between gap-3 flex-wrap mb-1">
          <h2 class="text-base font-semibold m-0 flex items-center gap-2"><i class="pi pi-key text-neutral-400"></i> رمز <code class="ltr">HuggingFace</code></h2>
          @if (hfToken(); as st) {
            @if (st.configured) {
              <p-tag [value]="(st.source === 'env' ? 'من البيئة' : 'مضبوط') + (st.hint ? ' · ' + st.hint : '')" severity="success" icon="pi pi-check" />
            } @else { <p-tag value="غير مضبوط" severity="warn" /> }
          }
        </div>
        <p class="text-neutral-500 text-sm mb-3">للنماذج/المجموعات الخاصة والمحمية. أنشئ رمزًا بصلاحية <code class="ltr">read</code> من
          <a class="ltr text-blue-600 dark:text-blue-400 no-underline hover:underline" href="https://huggingface.co/settings/tokens" target="_blank" rel="noopener">صفحة الرموز ↗</a>.</p>
        <div class="flex items-center gap-2">
          <input pInputText type="password" class="flex-1 min-w-0 ltr" [(ngModel)]="hfTokenInput" placeholder="hf_xxx… الصق الرمز هنا" (keydown.enter)="saveHfToken()" />
          <p-button label="حفظ" icon="pi pi-save" [loading]="savingHf()" [disabled]="!hfTokenInput.trim()" (onClick)="saveHfToken()" />
          @if (hfToken()?.configured) {
            <p-button label="مسح" icon="pi pi-trash" severity="danger" [outlined]="true" (onClick)="clearHfToken()" />
          }
        </div>
      </div>

      <!-- ── Generic API tokens ── -->
      <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-5 mb-5">
        <h2 class="text-base font-semibold m-0 mb-1">رموز أخرى <code class="ltr">API tokens</code></h2>
        <p class="text-neutral-500 text-sm mb-3">رموز إضافية تُحفظ محليًا (مثل مفاتيح خدمات خارجية). تُعرض مُقنّعة ولا تُرسَل لأي جهة.</p>

        @if (settings(); as st) {
          @if (tokenNames(st).length) {
            <div class="flex flex-col gap-2 mb-3">
              @for (name of tokenNames(st); track name) {
                <div class="flex items-center gap-3 px-3 py-2 rounded-lg border border-neutral-200 dark:border-neutral-800">
                  <span class="font-medium ltr">{{ name }}</span>
                  <span class="text-xs text-neutral-400 ltr">{{ st.tokens[name].hint }}</span>
                  <p-button icon="pi pi-trash" [text]="true" severity="danger" size="small" class="ms-auto" (onClick)="removeToken(name)" />
                </div>
              }
            </div>
          }
        }

        <div class="flex items-center gap-2">
          <input pInputText class="w-40 ltr" [(ngModel)]="newTokenName" placeholder="الاسم، مثال: openai" />
          <input pInputText type="password" class="flex-1 min-w-0 ltr" [(ngModel)]="newTokenValue" placeholder="القيمة (secret)" (keydown.enter)="addToken()" />
          <p-button label="إضافة" icon="pi pi-plus" [disabled]="!newTokenName.trim() || !newTokenValue.trim()" (onClick)="addToken()" />
        </div>
      </div>

      <!-- ── Appearance ── -->
      <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-5">
        <h2 class="text-base font-semibold m-0 mb-3">المظهر <code class="ltr">appearance</code></h2>
        <div class="flex gap-2">
          <button type="button" (click)="setTheme('light')"
            class="flex items-center gap-2 px-4 py-2 rounded-lg border text-sm transition-colors"
            [class]="theme() === 'light' ? 'border-blue-400 ring-1 ring-blue-400/40 bg-blue-50/50 dark:bg-blue-950/20' : 'border-neutral-200 dark:border-neutral-800 hover:border-neutral-300 dark:hover:border-neutral-700'">
            <i class="pi pi-sun"></i> فاتح
          </button>
          <button type="button" (click)="setTheme('dark')"
            class="flex items-center gap-2 px-4 py-2 rounded-lg border text-sm transition-colors"
            [class]="theme() === 'dark' ? 'border-blue-400 ring-1 ring-blue-400/40 bg-blue-50/50 dark:bg-blue-950/20' : 'border-neutral-200 dark:border-neutral-800 hover:border-neutral-300 dark:hover:border-neutral-700'">
            <i class="pi pi-moon"></i> داكن
          </button>
        </div>
      </div>
    </section>
  `,
})
export class SettingsPage implements OnInit {
  private api = inject(Api);
  private toast = inject(MessageService);

  readonly sys = signal<SystemInfo | null>(null);
  readonly settings = signal<AppSettings | null>(null);
  readonly hfToken = signal<{ configured: boolean; source: string | null; hint: string | null } | null>(null);
  readonly savingHf = signal(false);
  readonly theme = signal<Theme>('light');

  hfTokenInput = '';
  newTokenName = '';
  newTokenValue = '';

  ngOnInit(): void {
    this.reloadSystem();
    this.reloadSettings();
    this.api.hfTokenStatus().subscribe((s) => this.hfToken.set(s));
    this.theme.set((localStorage.getItem(THEME_KEY) as Theme) ?? 'light');
  }

  private reloadSystem(): void { this.api.system().subscribe((s) => this.sys.set(s)); }
  private reloadSettings(): void { this.api.getSettings().subscribe((s) => this.settings.set(s)); }

  // ── hardware ──
  /** The effective selection: the stored multi-select, else what the backend reports. */
  private selectedIndices(): number[] {
    const sel = this.settings()?.selected_gpu_indices;
    if (sel?.length) return sel;
    return (this.sys()?.selected_gpus ?? []).map((g) => g.index);
  }

  isSelected(g: GpuInfo): boolean { return this.selectedIndices().includes(g.index); }

  toggleGpu(index: number): void {
    const cur = this.selectedIndices();
    const next = cur.includes(index) ? cur.filter((i) => i !== index) : [...cur, index].sort((a, b) => a - b);
    // Empty selection ⇒ null (auto: largest GPU) so the backend never has zero GPUs.
    this.api.updateSettings({ selected_gpu_indices: next.length ? next : null }).subscribe((s) => {
      this.settings.set(s);
      this.reloadSystem();
      this.toast.add({ severity: 'success', summary: next.length > 1 ? `تم تحديد ${next.length} بطاقات` : 'تم تحديد بطاقة الرسوميات' });
    });
  }

  // ── HuggingFace token ──
  saveHfToken(): void {
    const t = this.hfTokenInput.trim();
    if (!t) return;
    this.savingHf.set(true);
    this.api.setHfToken(t).subscribe({
      next: (r) => {
        this.savingHf.set(false);
        this.hfTokenInput = '';
        this.api.hfTokenStatus().subscribe((s) => this.hfToken.set(s));
        this.toast.add({ severity: 'success', summary: 'تم حفظ الرمز', detail: r.username ? `مرحبًا ${r.username}` : '' });
      },
      error: (e) => {
        this.savingHf.set(false);
        this.toast.add({ severity: 'error', summary: 'رمز غير صالح', detail: String(e?.error?.detail ?? e.message), life: 7000 });
      },
    });
  }

  clearHfToken(): void {
    this.api.clearHfToken().subscribe(() => {
      this.api.hfTokenStatus().subscribe((s) => this.hfToken.set(s));
      this.toast.add({ severity: 'info', summary: 'تم مسح الرمز' });
    });
  }

  // ── generic API tokens ──
  tokenNames(st: AppSettings): string[] { return Object.keys(st.tokens ?? {}); }

  addToken(): void {
    const name = this.newTokenName.trim();
    const value = this.newTokenValue.trim();
    if (!name || !value) return;
    this.api.updateSettings({ tokens: { [name]: value } }).subscribe((s) => {
      this.settings.set(s);
      this.newTokenName = '';
      this.newTokenValue = '';
      this.toast.add({ severity: 'success', summary: 'تم حفظ الرمز', detail: name });
    });
  }

  removeToken(name: string): void {
    this.api.updateSettings({ tokens: { [name]: null } }).subscribe((s) => {
      this.settings.set(s);
      this.toast.add({ severity: 'info', summary: 'تم حذف الرمز', detail: name });
    });
  }

  // ── appearance ──
  setTheme(t: Theme): void {
    this.theme.set(t);
    document.documentElement.classList.toggle('dark', t === 'dark');
    localStorage.setItem(THEME_KEY, t);
    this.api.updateSettings({ theme: t }).subscribe({ next: () => {}, error: () => {} });
  }
}
