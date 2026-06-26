import { Component, Input, OnInit, inject, signal } from '@angular/core';
import { NgClass } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { TextareaModule } from 'primeng/textarea';
import { TagModule } from 'primeng/tag';
import { TooltipModule } from 'primeng/tooltip';
import { SelectModule } from 'primeng/select';
import { DialogModule } from 'primeng/dialog';
import { CheckboxModule } from 'primeng/checkbox';
import { MessageService } from 'primeng/api';
import { Api } from '../../core/api';
import { MarkdownPipe } from '../../core/markdown.pipe';
import { ChatMessage, ChatSession, ModelVersion, Project } from '../../core/types';

@Component({
  selector: 'app-chat-panel',
  imports: [NgClass, FormsModule, ButtonModule, InputTextModule, TextareaModule, TagModule, TooltipModule, SelectModule, DialogModule, CheckboxModule, MarkdownPipe],
  template: `
    <div class="flex gap-4 h-[calc(100vh-12rem)]">
      <!-- sessions rail -->
      <aside class="w-64 shrink-0 flex flex-col p-3 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900">
        <div class="flex items-center justify-between mb-2">
          <span class="font-bold">الجلسات</span>
          <div class="flex">
            <p-button icon="pi pi-clone" [rounded]="true" [text]="true" size="small" pTooltip="استيراد محادثات من مشروع آخر" (onClick)="openImport()" />
            <p-button icon="pi pi-plus" [rounded]="true" [text]="true" size="small" pTooltip="جلسة جديدة" (onClick)="newSession()" />
          </div>
        </div>
        <div class="flex flex-col gap-1 overflow-auto">
          @for (s of sessions(); track s.id) {
            <button class="flex items-center gap-2 px-2.5 py-2 rounded-lg text-start transition-colors"
                    [ngClass]="s.id === current()?.id
                      ? 'bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300'
                      : 'text-neutral-700 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-800/50'"
                    (click)="open(s.id)" type="button">
              <i class="pi pi-comment"></i>
              <span class="flex-1 truncate text-sm">{{ s.title }}</span>
              @if (s.approved_count > 0) { <span class="text-xs font-bold rounded-full px-1.5 bg-blue-600 text-white">{{ s.approved_count }}</span> }
            </button>
          }
          @if (sessions().length === 0) { <p class="p-2 text-xs text-neutral-400">لا جلسات بعد — ابدأ واحدة.</p> }
        </div>
      </aside>

      <!-- conversation -->
      <section class="flex-1 flex flex-col overflow-hidden rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900">
        @if (current(); as s) {
          <header class="flex items-center justify-between gap-3 px-4 py-3 border-b border-neutral-200 dark:border-neutral-800">
            <input pInputText class="flex-1 min-w-0 bg-transparent border-0 px-0 font-bold text-base focus:outline-none" [(ngModel)]="s.title" (blur)="renameSession(s)" />
            <div class="flex items-center gap-3 shrink-0">
              <p-button icon="pi pi-cog" [text]="true" size="small" label="تعليمات النظام" pTooltip="تعليمات النظام (system prompt)" (onClick)="openSysPrompt(s)" />
              <p-button icon="pi pi-sparkles" [text]="true" size="small" label="تعليمات التحسين" pTooltip="تعليمات التحسين الذاتي (correction prompt)" (onClick)="openCorrectionPrompt(s)" />
              <!-- which model is this chat talking to -->
              <div class="flex items-center gap-2" pTooltip="النموذج الذي تحادثه في هذه الجلسة">
                @if (s.is_base_model) {
                  <p-tag value="النموذج الأساسي" severity="contrast" icon="pi pi-box" />
                } @else {
                  <p-tag value="نموذج مُدرَّب" severity="success" icon="pi pi-sparkles" />
                }
                <p-select [options]="versionOptions()" optionLabel="label" optionValue="id"
                          [ngModel]="s.model_version_id" (onChange)="switchModel(s, $event.value)"
                          styleClass="ver-sel" appendTo="body" />
              </div>
              <span class="text-xs whitespace-nowrap text-neutral-500 dark:text-neutral-400"><i class="pi pi-database"></i> {{ s.approved_count }} مثال تدريب</span>
            </div>
          </header>

          <div class="flex-1 overflow-auto p-4 flex flex-col gap-4">
            @for (m of s.messages; track m.id) {
              <div class="flex gap-2"
                   [ngClass]="{
                     'flex-row-reverse ms-auto': m.role === 'user',
                     'max-w-full w-full': editingId() === m.id,
                     'max-w-[86%]': editingId() !== m.id
                   }">
                <div class="text-xl shrink-0">{{ m.role === 'user' ? '🧑' : '🕯️' }}</div>
                <div class="rounded-2xl px-4 py-2"
                     [ngClass]="{
                       'bg-blue-600 text-white': m.role === 'user',
                       'bg-neutral-100 dark:bg-neutral-800': m.role === 'assistant',
                       'flex-1': editingId() === m.id
                     }">
                  @if (editingId() === m.id) {
                    <div class="flex items-center gap-1.5 mb-2 text-xs text-neutral-500 dark:text-neutral-400"><i class="pi pi-pencil"></i> تصحيح الرد — اكتب ما كان يجب أن يقوله النموذج</div>
                    <textarea pTextarea [(ngModel)]="editText" class="w-full min-h-[260px] resize-y" autofocus></textarea>
                    <div class="flex gap-2 mt-3">
                      <p-button label="حفظ التصحيح" icon="pi pi-check" (onClick)="saveEdit(m)" />
                      <p-button label="إلغاء" severity="secondary" [text]="true" (onClick)="editingId.set(null)" />
                    </div>
                  } @else {
                    @if (m.role === 'assistant') {
                      <div class="leading-7 break-words [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&_h1]:text-lg [&_h1]:font-bold [&_h1]:my-2 [&_h2]:text-base [&_h2]:font-bold [&_h2]:my-2 [&_h3]:text-sm [&_h3]:font-bold [&_h3]:my-2 [&_p]:my-2 [&_ul]:my-2 [&_ul]:ps-6 [&_ul]:list-disc [&_ol]:my-2 [&_ol]:ps-6 [&_ol]:list-decimal [&_li]:my-0.5 [&_a]:text-blue-600 dark:[&_a]:text-blue-400 [&_a]:underline [&_code]:font-mono [&_code]:text-[0.86em] [&_code]:bg-neutral-200/60 dark:[&_code]:bg-neutral-700/60 [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded [&_pre]:bg-neutral-50 dark:[&_pre]:bg-neutral-950 [&_pre]:border [&_pre]:border-neutral-200 dark:[&_pre]:border-neutral-800 [&_pre]:rounded-lg [&_pre]:p-3 [&_pre]:overflow-auto [&_pre]:text-left [&_pre]:[direction:ltr] [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_blockquote]:border-s-2 [&_blockquote]:border-neutral-300 dark:[&_blockquote]:border-neutral-700 [&_blockquote]:ps-3 [&_blockquote]:text-neutral-500 [&_table]:w-full [&_table]:border-collapse [&_table]:my-2 [&_th]:border [&_th]:border-neutral-200 dark:[&_th]:border-neutral-800 [&_th]:p-2 [&_th]:bg-neutral-100 dark:[&_th]:bg-neutral-800 [&_th]:font-bold [&_th]:text-start [&_td]:border [&_td]:border-neutral-200 dark:[&_td]:border-neutral-800 [&_td]:p-2 [&_td]:text-start" [innerHTML]="displayContent(m) | markdown"></div>
                    } @else {
                      <p class="m-0 whitespace-pre-wrap leading-7">{{ m.content }}</p>
                    }
                    @if (showCaret(m)) { <span class="inline-block ms-0.5 text-blue-600 dark:text-blue-400 animate-pulse">▍</span> }
                    <div class="flex gap-1 mt-2">
                      @if (m.corrected) { <p-tag value="معدّل" severity="warn" icon="pi pi-pencil" /> }
                      @if (isSelfCorrected(m)) { <p-tag value="تحسين ذاتي" severity="info" icon="pi pi-sparkles" /> }
                      @if (m.approved) { <p-tag value="معتمد للتدريب" severity="success" icon="pi pi-check" /> }
                    </div>
                    @if (m.role === 'assistant' && isPersisted(m)) {
                      <div class="flex flex-wrap gap-1 mt-1">
                        <p-button icon="pi pi-pencil" [text]="true" size="small" label="تصحيح"
                                  [disabled]="correcting() !== null" (onClick)="startEdit(m)" />
                        <p-button icon="pi pi-sparkles" [text]="true" size="small" label="تحسين ذاتي"
                                  pTooltip="اطلب من النموذج تحسين رده بنفسه"
                                  [loading]="correcting() === m.id" [disabled]="correcting() !== null || thinking()"
                                  (onClick)="selfCorrect(m)" />
                        <p-button [icon]="m.approved ? 'pi pi-star-fill' : 'pi pi-star'" [text]="true" size="small"
                                  [label]="m.approved ? 'إلغاء الاعتماد' : 'اعتماد'"
                                  [disabled]="correcting() !== null" (onClick)="toggleApprove(m)" />
                        @if (m.corrected && m.original_content) {
                          <p-button [icon]="isShowingOriginal(m) ? 'pi pi-eye-slash' : 'pi pi-history'" [text]="true" size="small"
                                    [label]="isShowingOriginal(m) ? 'عرض المُحسّن' : 'عرض الأصل'" (onClick)="toggleOriginal(m)" />
                        }
                        @if (isLast(m)) {
                          <p-button icon="pi pi-refresh" [text]="true" size="small" label="إعادة توليد"
                                    [disabled]="correcting() !== null" (onClick)="regenerate()" />
                        }
                      </div>
                    } @else if (m.role === 'assistant' && !isPersisted(m)) {
                      <div class="mt-1 text-xs text-neutral-400">…سيمكن التصحيح بعد اكتمال الرد</div>
                    }
                  }
                </div>
              </div>
            }
          </div>

          <footer class="flex items-end gap-2 p-3 border-t border-neutral-200 dark:border-neutral-800">
            <textarea pTextarea rows="2" [(ngModel)]="draft" (keydown.enter)="$event.preventDefault(); send()"
                      placeholder="اكتب رسالتك… ثم صحّح رد النموذج ليتعلّم منه" class="flex-1 resize-none"></textarea>
            <p-button icon="pi pi-send" [rounded]="true" [disabled]="!draft.trim() || thinking()" (onClick)="send()" />
          </footer>
        } @else {
          <div class="flex flex-col items-center justify-center h-full gap-2 text-neutral-500 dark:text-neutral-400">
            <span class="text-5xl">💬</span>
            <p>اختر جلسة أو أنشئ واحدة جديدة لبدء المحادثة والتصحيح.</p>
          </div>
        }
      </section>
    </div>

    <!-- system prompt editor -->
    <p-dialog header="تعليمات النظام · system prompt" [(visible)]="showSysPrompt" [modal]="true"
              [style]="{ width: '640px', maxWidth: '94vw' }" [dismissableMask]="true">
      <p class="mt-0 mb-3 text-xs text-neutral-500 dark:text-neutral-400">توجيه يُضاف قبل كل محادثة في هذه الجلسة لضبط أسلوب النموذج.</p>
      <textarea pTextarea [(ngModel)]="sysPromptDraft" class="w-full min-h-[180px] leading-8 resize-y" placeholder="مثال: أنت مساعد عربي مفيد ودقيق، تجيب بإيجاز وباللغة العربية الفصحى."></textarea>
      <ng-template pTemplate="footer">
        <p-button label="إلغاء" severity="secondary" [text]="true" (onClick)="showSysPrompt = false" />
        <p-button label="حفظ" icon="pi pi-check" (onClick)="saveSysPrompt()" />
      </ng-template>
    </p-dialog>

    <!-- self-correction prompt editor (the "magic wand") -->
    <p-dialog header="تعليمات التحسين الذاتي · correction prompt" [(visible)]="showCorrectionPrompt" [modal]="true"
              [style]="{ width: '640px', maxWidth: '94vw' }" [dismissableMask]="true">
      <p class="mt-0 mb-3 text-xs text-neutral-500 dark:text-neutral-400">توجيه يُملي على النموذج كيف يُحسّن ردّه عند الضغط على زر «تحسين ذاتي» (لغة، منطق، تفكير من المبادئ الأولى، وتنسيق Markdown). اتركه فارغًا لاستخدام التعليمات الافتراضية.</p>
      <textarea pTextarea [(ngModel)]="correctionPromptDraft" class="w-full min-h-[180px] leading-8 resize-y"
                [placeholder]="correctionPromptPlaceholder"></textarea>
      <ng-template pTemplate="footer">
        <p-button label="إلغاء" severity="secondary" [text]="true" (onClick)="showCorrectionPrompt = false" />
        <p-button label="حفظ" icon="pi pi-check" (onClick)="saveCorrectionPrompt()" />
      </ng-template>
    </p-dialog>

    <!-- inherit chats from other projects -->
    <p-dialog header="استيراد محادثات من مشروع آخر" [(visible)]="showImport" [modal]="true"
              [style]="{ width: '720px', maxWidth: '94vw' }" [dismissableMask]="true">
      <p class="mt-0 mb-3 text-xs text-neutral-500 dark:text-neutral-400">انسخ جلسات (مع تصحيحاتها) من مشروع آخر إلى هذا المشروع لإعادة استخدامها في التدريب.</p>
      <label class="block mt-2 mb-1.5 font-semibold">المشروع المصدر</label>
      <p-select [options]="otherProjects()" optionLabel="name" optionValue="id" [(ngModel)]="importSourceId"
                (onChange)="loadSourceSessions($event.value)" placeholder="اختر مشروعًا" styleClass="w-full" appendTo="body" />

      @if (importSourceId) {
        <div class="flex flex-col gap-0.5 mt-3 max-h-80 overflow-auto">
          @for (s of sourceSessions(); track s.id) {
            <label class="flex items-center gap-2.5 px-2.5 py-2 rounded-lg cursor-pointer transition-colors hover:bg-neutral-50 dark:hover:bg-neutral-800/50">
              <p-checkbox [binary]="true" [ngModel]="isPicked(s.id)" (ngModelChange)="togglePick(s.id)" />
              <span class="flex-1 text-sm">{{ s.title }}</span>
              <span class="text-xs text-neutral-400">{{ s.approved_count }} مثال معتمد</span>
            </label>
          }
          @if (sourceSessions().length === 0) { <p class="text-neutral-400">لا جلسات في هذا المشروع.</p> }
        </div>
      }
      <ng-template pTemplate="footer">
        <p-button label="إلغاء" severity="secondary" [text]="true" (onClick)="showImport = false" />
        <p-button label="استيراد المحدد" icon="pi pi-clone" [disabled]="picked().length === 0" [loading]="importing()" (onClick)="doImport()" />
      </ng-template>
    </p-dialog>
  `,
})
export class ChatPanel implements OnInit {
  @Input() projectId!: string;
  private api = inject(Api);
  private toast = inject(MessageService);

  readonly sessions = signal<ChatSession[]>([]);
  readonly current = signal<ChatSession | null>(null);
  readonly thinking = signal(false);
  readonly editingId = signal<string | null>(null);
  readonly versionOptions = signal<{ id: string; label: string }[]>([]);
  draft = '';
  editText = '';

  // system prompt editor
  showSysPrompt = false;
  sysPromptDraft = '';
  private sysPromptSession: ChatSession | null = null;

  // self-correction ("magic wand")
  readonly correcting = signal<string | null>(null);        // message id being corrected
  readonly showOriginalIds = signal<Set<string>>(new Set()); // messages viewing their original draft
  showCorrectionPrompt = false;
  correctionPromptDraft = '';
  private correctionPromptSession: ChatSession | null = null;
  readonly correctionPromptPlaceholder =
    'اتركه فارغًا لاستخدام التعليمات الافتراضية: تصحيح اللغة والمنطق، التفكير من المبادئ الأولى، والتنسيق بعناوين Markdown وجداول.';

  // import-from-other-project dialog
  showImport = false;
  importing = signal(false);
  importSourceId: string | null = null;
  readonly otherProjects = signal<Project[]>([]);
  readonly sourceSessions = signal<ChatSession[]>([]);
  readonly picked = signal<string[]>([]);

  ngOnInit(): void {
    this.loadSessions();
    this.loadVersions();
  }

  // ── system prompt ──
  openSysPrompt(s: ChatSession): void {
    this.sysPromptSession = s;
    this.sysPromptDraft = s.system_prompt ?? '';
    this.showSysPrompt = true;
  }
  saveSysPrompt(): void {
    const s = this.sysPromptSession; if (!s) return;
    this.api.updateSession(s.id, { system_prompt: this.sysPromptDraft }).subscribe(() => {
      this.showSysPrompt = false;
      this.open(s.id);
      this.toast.add({ severity: 'success', summary: 'حُفظت تعليمات النظام' });
    });
  }

  // ── self-correction prompt editor ──
  openCorrectionPrompt(s: ChatSession): void {
    this.correctionPromptSession = s;
    this.correctionPromptDraft = s.correction_prompt ?? '';
    this.showCorrectionPrompt = true;
  }
  saveCorrectionPrompt(): void {
    const s = this.correctionPromptSession; if (!s) return;
    this.api.updateSession(s.id, { correction_prompt: this.correctionPromptDraft }).subscribe(() => {
      this.showCorrectionPrompt = false;
      this.open(s.id);
      this.toast.add({ severity: 'success', summary: 'حُفظت تعليمات التحسين' });
    });
  }

  // ── self-correction ("magic wand") ──
  isSelfCorrected(m: ChatMessage): boolean { return m.meta?.['self_corrected'] === true; }
  isShowingOriginal(m: ChatMessage): boolean { return this.showOriginalIds().has(m.id); }
  toggleOriginal(m: ChatMessage): void {
    const next = new Set(this.showOriginalIds());
    if (next.has(m.id)) next.delete(m.id); else next.add(m.id);
    this.showOriginalIds.set(next);
  }
  displayContent(m: ChatMessage): string {
    return this.isShowingOriginal(m) ? (m.original_content ?? m.content) : m.content;
  }
  showCaret(m: ChatMessage): boolean {
    return (this.thinking() && this.isLast(m) && m.role === 'assistant') || this.correcting() === m.id;
  }

  /** Ask the model to improve its own reply; stream the improved text in place. */
  selfCorrect(m: ChatMessage): void {
    const s = this.current();
    if (!s || !this.isPersisted(m) || this.correcting() || this.thinking()) return;
    if (this.isShowingOriginal(m)) this.toggleOriginal(m);   // view the improved version while it streams
    this.correcting.set(m.id);
    // stash the first draft and clear content so tokens stream in fresh
    this.updateMsg(m.id, (x) => ({ ...x, original_content: x.original_content ?? x.content, content: '' }));
    const body: Record<string, unknown> = s.correction_prompt ? { correction_prompt: s.correction_prompt } : {};
    this.api.selfCorrectStream(m.id, body, {
      onToken: (t) => this.appendToken(m.id, t),
      onDone: () => {
        this.correcting.set(null);
        this.open(s.id);          // reload → persisted content + "تحسين ذاتي" tag
        this.refreshList();
      },
      onError: (msg) => {
        this.correcting.set(null);
        const soft = /runtime|install|importable|torch|transformers/i.test(msg);
        this.toast.add({
          severity: soft ? 'warn' : 'error', summary: 'تعذّر التحسين',
          detail: soft ? 'لم يتم تثبيت بيئة النموذج بعد (راجع requirements-ml.txt).' : msg,
          life: 6000,
        });
        this.open(s.id);          // restore the original reply on failure
      },
    });
  }

  // ── import chats from other projects ──
  openImport(): void {
    this.importSourceId = null;
    this.sourceSessions.set([]);
    this.picked.set([]);
    this.api.listProjects().subscribe((ps) =>
      this.otherProjects.set(ps.filter((p) => p.id !== this.projectId)));
    this.showImport = true;
  }
  loadSourceSessions(projectId: string): void {
    this.picked.set([]);
    this.api.listSessions(projectId).subscribe((s) => this.sourceSessions.set(s));
  }
  isPicked(id: string): boolean { return this.picked().includes(id); }
  togglePick(id: string): void {
    const cur = this.picked();
    this.picked.set(cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]);
  }
  doImport(): void {
    if (this.picked().length === 0) return;
    this.importing.set(true);
    this.api.importSessions(this.projectId, this.picked()).subscribe({
      next: (created) => {
        this.importing.set(false);
        this.showImport = false;
        this.loadSessions();
        this.toast.add({ severity: 'success', summary: 'تم الاستيراد', detail: `${created.length} جلسة` });
      },
      error: (e) => {
        this.importing.set(false);
        this.toast.add({ severity: 'error', summary: 'تعذّر الاستيراد', detail: String(e?.error?.detail ?? e.message) });
      },
    });
  }

  loadVersions(): void {
    this.api.listVersions(this.projectId).subscribe((vs: ModelVersion[]) => {
      this.versionOptions.set(vs.map((v) => ({
        id: v.id,
        label: (v.is_base ? '◦ ' : '★ ') + v.label + (v.is_active ? ' (نشط)' : ''),
      })));
    });
  }

  switchModel(s: ChatSession, versionId: string): void {
    this.api.updateSession(s.id, { model_version_id: versionId }).subscribe((upd) => {
      // refresh the open session so the badge + subsequent replies use the new model
      this.open(upd.id);
    });
  }

  loadSessions(): void {
    this.api.listSessions(this.projectId).subscribe((s) => {
      this.sessions.set(s);
      if (!this.current() && s.length) this.open(s[0].id);
    });
  }

  open(id: string): void {
    this.api.getSession(id).subscribe((s) => this.current.set(s));
  }

  newSession(): void {
    this.api.createSession(this.projectId, { title: 'جلسة جديدة', system_prompt: 'أنت مساعد عربي مفيد ودقيق.' })
      .subscribe((s) => { this.loadSessions(); this.current.set(s); });
  }

  renameSession(s: ChatSession): void {
    this.api.updateSession(s.id, { title: s.title }).subscribe(() => this.refreshList());
  }

  /** Stream the reply token-by-token into an optimistic assistant bubble. */
  send(): void {
    const s = this.current();
    if (!s || !this.draft.trim() || this.thinking()) return;
    const text = this.draft.trim();
    this.draft = '';
    this.thinking.set(true);

    const stamp = Date.now();
    const tmpUser = 'tmp-u-' + stamp;
    const tmpAsst = 'tmp-a-' + stamp;
    const now = new Date().toISOString();
    const mk = (role: 'user' | 'assistant', content: string, id: string): ChatMessage => ({
      id, session_id: s.id, role, content, original_content: null,
      corrected: false, approved: false, include_in_training: true,
      order_index: 0, created_at: now, meta: {},
    });
    this.current.set({ ...s, messages: [...s.messages, mk('user', text, tmpUser), mk('assistant', '', tmpAsst)] });

    this.api.chatStream(s.id, { content: text }, {
      onUser: (p) => this.setMsgId(tmpUser, p.id),
      onToken: (t) => this.appendToken(tmpAsst, t),
      onDone: (p) => {
        this.thinking.set(false);
        this.setMsgId(tmpAsst, p.id, p.content);
        this.refreshList();
      },
      onError: (msg) => {
        this.thinking.set(false);
        const soft = /runtime|install|importable|torch|transformers/i.test(msg);
        this.toast.add({
          severity: soft ? 'warn' : 'error', summary: 'تعذر التوليد',
          detail: soft ? 'لم يتم تثبيت بيئة النموذج بعد (راجع requirements-ml.txt).' : msg,
          life: 6000,
        });
        this.open(s.id);
      },
    });
  }

  private appendToken(id: string, t: string): void {
    this.updateMsg(id, (m) => ({ ...m, content: m.content + t }));
  }
  private setMsgId(oldId: string, newId: string, content?: string): void {
    this.updateMsg(oldId, (m) => ({ ...m, id: newId, ...(content != null ? { content } : {}) }));
  }
  private updateMsg(id: string, fn: (m: ChatMessage) => ChatMessage): void {
    const s = this.current(); if (!s) return;
    this.current.set({ ...s, messages: s.messages.map((m) => (m.id === id ? fn(m) : m)) });
  }

  regenerate(): void {
    const s = this.current();
    if (!s) return;
    this.thinking.set(true);
    this.api.regenerate(s.id).subscribe({
      next: () => { this.thinking.set(false); this.open(s.id); },
      error: () => { this.thinking.set(false); this.open(s.id); },
    });
  }

  /** A message is editable only once it's persisted (not a streaming temp id). */
  isPersisted(m: ChatMessage): boolean { return !m.id.startsWith('tmp-'); }

  startEdit(m: ChatMessage): void {
    if (!this.isPersisted(m)) return;       // can't edit a reply that's still streaming
    this.editingId.set(m.id);
    this.editText = m.content;
  }

  saveEdit(m: ChatMessage): void {
    if (!this.isPersisted(m)) {
      this.toast.add({ severity: 'warn', summary: 'انتظر اكتمال الرد', detail: 'لا يمكن حفظ التصحيح قبل انتهاء التوليد.' });
      return;
    }
    this.api.editMessage(m.id, { content: this.editText }).subscribe({
      next: (upd) => {
        this.editingId.set(null);
        this.replace(upd);
        this.refreshList();
        this.toast.add({ severity: 'success', summary: 'حُفظ التصحيح', detail: 'أصبح هذا الرد مثال تدريب معتمد.' });
      },
      error: (e) => {
        // keep the edit box open so the user's text isn't lost
        this.toast.add({
          severity: 'error', summary: 'تعذّر حفظ التصحيح',
          detail: String(e?.error?.detail ?? e?.message ?? e), life: 7000,
        });
      },
    });
  }

  toggleApprove(m: ChatMessage): void {
    if (!this.isPersisted(m)) return;
    this.api.editMessage(m.id, { approved: !m.approved }).subscribe({
      next: (upd) => { this.replace(upd); this.refreshList(); },
      error: (e) => this.toast.add({ severity: 'error', summary: 'تعذّر التحديث', detail: String(e?.error?.detail ?? e?.message ?? e) }),
    });
  }

  isLast(m: ChatMessage): boolean {
    const msgs = this.current()?.messages ?? [];
    return msgs.length > 0 && msgs[msgs.length - 1].id === m.id;
  }

  private replace(upd: ChatMessage): void {
    const s = this.current(); if (!s) return;
    this.current.set({ ...s, messages: s.messages.map((x) => (x.id === upd.id ? upd : x)) });
  }
  private refreshList(): void {
    this.api.listSessions(this.projectId).subscribe((s) => this.sessions.set(s));
  }
}
