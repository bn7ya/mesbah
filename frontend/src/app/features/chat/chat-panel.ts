import { Component, Input, OnInit, inject, signal } from '@angular/core';
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
  imports: [FormsModule, ButtonModule, InputTextModule, TextareaModule, TagModule, TooltipModule, SelectModule, DialogModule, CheckboxModule, MarkdownPipe],
  template: `
    <div class="chat-layout">
      <!-- sessions rail -->
      <aside class="rail glass">
        <div class="rail-head">
          <span class="t">الجلسات</span>
          <div class="rail-actions">
            <p-button icon="pi pi-clone" [rounded]="true" [text]="true" size="small" pTooltip="استيراد محادثات من مشروع آخر" (onClick)="openImport()" />
            <p-button icon="pi pi-plus" [rounded]="true" [text]="true" size="small" pTooltip="جلسة جديدة" (onClick)="newSession()" />
          </div>
        </div>
        <div class="sessions">
          @for (s of sessions(); track s.id) {
            <button class="srow" [class.sel]="s.id === current()?.id" (click)="open(s.id)" type="button">
              <i class="pi pi-comment"></i>
              <span class="st">{{ s.title }}</span>
              @if (s.approved_count > 0) { <span class="cnt">{{ s.approved_count }}</span> }
            </button>
          }
          @if (sessions().length === 0) { <p class="muted dim hint">لا جلسات بعد — ابدأ واحدة.</p> }
        </div>
      </aside>

      <!-- conversation -->
      <section class="conv glass">
        @if (current(); as s) {
          <header class="conv-head">
            <input pInputText class="title-in" [(ngModel)]="s.title" (blur)="renameSession(s)" />
            <div class="head-right">
              <p-button icon="pi pi-cog" [text]="true" size="small" label="تعليمات النظام" pTooltip="تعليمات النظام (system prompt)" (onClick)="openSysPrompt(s)" />
              <p-button icon="pi pi-sparkles" [text]="true" size="small" label="تعليمات التحسين" pTooltip="تعليمات التحسين الذاتي (correction prompt)" (onClick)="openCorrectionPrompt(s)" />
              <!-- which model is this chat talking to -->
              <div class="model-of" pTooltip="النموذج الذي تحادثه في هذه الجلسة">
                @if (s.is_base_model) {
                  <p-tag value="النموذج الأساسي" severity="contrast" icon="pi pi-box" />
                } @else {
                  <p-tag value="نموذج مُدرَّب" severity="success" icon="pi pi-sparkles" />
                }
                <p-select [options]="versionOptions()" optionLabel="label" optionValue="id"
                          [ngModel]="s.model_version_id" (onChange)="switchModel(s, $event.value)"
                          styleClass="ver-sel" appendTo="body" />
              </div>
              <span class="muted dim approved"><i class="pi pi-database"></i> {{ s.approved_count }} مثال تدريب</span>
            </div>
          </header>

          <div class="stream">
            @for (m of s.messages; track m.id) {
              <div class="msg" [class.user]="m.role === 'user'" [class.assistant]="m.role === 'assistant'"
                   [class.editing]="editingId() === m.id">
                <div class="avatar">{{ m.role === 'user' ? '🧑' : '🕯️' }}</div>
                <div class="bubble glass">
                  @if (editingId() === m.id) {
                    <div class="edit-head muted small"><i class="pi pi-pencil"></i> تصحيح الرد — اكتب ما كان يجب أن يقوله النموذج</div>
                    <textarea pTextarea [(ngModel)]="editText" class="edit-area" autofocus></textarea>
                    <div class="edit-actions">
                      <p-button label="حفظ التصحيح" icon="pi pi-check" (onClick)="saveEdit(m)" />
                      <p-button label="إلغاء" severity="secondary" [text]="true" (onClick)="editingId.set(null)" />
                    </div>
                  } @else {
                    @if (m.role === 'assistant') {
                      <div class="content md" [innerHTML]="displayContent(m) | markdown"></div>
                    } @else {
                      <p class="content">{{ m.content }}</p>
                    }
                    @if (showCaret(m)) { <span class="caret">▍</span> }
                    <div class="tags">
                      @if (m.corrected) { <p-tag value="معدّل" severity="warn" icon="pi pi-pencil" /> }
                      @if (isSelfCorrected(m)) { <p-tag value="تحسين ذاتي" severity="info" icon="pi pi-sparkles" /> }
                      @if (m.approved) { <p-tag value="معتمد للتدريب" severity="success" icon="pi pi-check" /> }
                    </div>
                    @if (m.role === 'assistant' && isPersisted(m)) {
                      <div class="msg-actions">
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
                      <div class="msg-actions dim small">…سيمكن التصحيح بعد اكتمال الرد</div>
                    }
                  }
                </div>
              </div>
            }
          </div>

          <footer class="composer">
            <textarea pTextarea rows="2" [(ngModel)]="draft" (keydown.enter)="$event.preventDefault(); send()"
                      placeholder="اكتب رسالتك… ثم صحّح رد النموذج ليتعلّم منه" class="composer-in"></textarea>
            <p-button icon="pi pi-send" [rounded]="true" [disabled]="!draft.trim() || thinking()" (onClick)="send()" />
          </footer>
        } @else {
          <div class="empty muted">
            <span class="big">💬</span>
            <p>اختر جلسة أو أنشئ واحدة جديدة لبدء المحادثة والتصحيح.</p>
          </div>
        }
      </section>
    </div>

    <!-- system prompt editor -->
    <p-dialog header="تعليمات النظام · system prompt" [(visible)]="showSysPrompt" [modal]="true"
              [style]="{ width: '640px', maxWidth: '94vw' }" [dismissableMask]="true">
      <p class="muted small dlg-sub">توجيه يُضاف قبل كل محادثة في هذه الجلسة لضبط أسلوب النموذج.</p>
      <textarea pTextarea [(ngModel)]="sysPromptDraft" class="sys-area" placeholder="مثال: أنت مساعد عربي مفيد ودقيق، تجيب بإيجاز وباللغة العربية الفصحى."></textarea>
      <ng-template pTemplate="footer">
        <p-button label="إلغاء" severity="secondary" [text]="true" (onClick)="showSysPrompt = false" />
        <p-button label="حفظ" icon="pi pi-check" (onClick)="saveSysPrompt()" />
      </ng-template>
    </p-dialog>

    <!-- self-correction prompt editor (the "magic wand") -->
    <p-dialog header="تعليمات التحسين الذاتي · correction prompt" [(visible)]="showCorrectionPrompt" [modal]="true"
              [style]="{ width: '640px', maxWidth: '94vw' }" [dismissableMask]="true">
      <p class="muted small dlg-sub">توجيه يُملي على النموذج كيف يُحسّن ردّه عند الضغط على زر «تحسين ذاتي» (لغة، منطق، تفكير من المبادئ الأولى، وتنسيق Markdown). اتركه فارغًا لاستخدام التعليمات الافتراضية.</p>
      <textarea pTextarea [(ngModel)]="correctionPromptDraft" class="sys-area"
                [placeholder]="correctionPromptPlaceholder"></textarea>
      <ng-template pTemplate="footer">
        <p-button label="إلغاء" severity="secondary" [text]="true" (onClick)="showCorrectionPrompt = false" />
        <p-button label="حفظ" icon="pi pi-check" (onClick)="saveCorrectionPrompt()" />
      </ng-template>
    </p-dialog>

    <!-- inherit chats from other projects -->
    <p-dialog header="استيراد محادثات من مشروع آخر" [(visible)]="showImport" [modal]="true"
              [style]="{ width: '720px', maxWidth: '94vw' }" [dismissableMask]="true">
      <p class="muted small dlg-sub">انسخ جلسات (مع تصحيحاتها) من مشروع آخر إلى هذا المشروع لإعادة استخدامها في التدريب.</p>
      <label class="lbl">المشروع المصدر</label>
      <p-select [options]="otherProjects()" optionLabel="name" optionValue="id" [(ngModel)]="importSourceId"
                (onChange)="loadSourceSessions($event.value)" placeholder="اختر مشروعًا" styleClass="full" appendTo="body" />

      @if (importSourceId) {
        <div class="src-list">
          @for (s of sourceSessions(); track s.id) {
            <label class="src-row">
              <p-checkbox [binary]="true" [ngModel]="isPicked(s.id)" (ngModelChange)="togglePick(s.id)" />
              <span class="src-title">{{ s.title }}</span>
              <span class="src-meta dim">{{ s.approved_count }} مثال معتمد</span>
            </label>
          }
          @if (sourceSessions().length === 0) { <p class="muted dim">لا جلسات في هذا المشروع.</p> }
        </div>
      }
      <ng-template pTemplate="footer">
        <p-button label="إلغاء" severity="secondary" [text]="true" (onClick)="showImport = false" />
        <p-button label="استيراد المحدد" icon="pi pi-clone" [disabled]="picked().length === 0" [loading]="importing()" (onClick)="doImport()" />
      </ng-template>
    </p-dialog>
  `,
  styles: [`
    .chat-layout { display: grid; grid-template-columns: 260px 1fr; gap: 0.9rem; height: 68vh; }
    .rail { padding: 0.8rem; display: flex; flex-direction: column; }
    .rail-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
    .rail-head .t { font-weight: 700; }
    .small { font-size: 0.75rem; }
    .rail-actions { display: flex; gap: 0.1rem; }
    .dlg-sub { margin: 0 0 0.8rem; }
    .lbl { font-weight: 600; display: block; margin: 0.4rem 0 0.3rem; }
    .full { width: 100%; }
    .sys-area { width: 100%; min-height: 180px; font-size: 0.95rem; line-height: 1.8; resize: vertical; }
    .src-list { display: flex; flex-direction: column; gap: 0.2rem; margin-top: 0.8rem; max-height: 320px; overflow: auto; }
    .src-row { display: flex; align-items: center; gap: 0.6rem; padding: 0.5rem 0.6rem; border-radius: 10px; cursor: pointer; }
    .src-row:hover { background: var(--glass-bg); }
    .src-title { flex: 1; font-size: 0.9rem; }
    .src-meta { font-size: 0.76rem; }
    .sessions { display: flex; flex-direction: column; gap: 0.3rem; overflow: auto; }
    .srow { display: flex; align-items: center; gap: 0.5rem; padding: 0.55rem 0.6rem; border-radius: 10px; background: transparent; border: 1px solid transparent; color: var(--text-2); cursor: pointer; text-align: start; }
    .srow:hover { background: var(--glass-bg); color: var(--text-1); }
    .srow.sel { background: var(--glass-bg-strong); color: var(--text-1); border-color: var(--glass-border); }
    .srow .st { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 0.86rem; }
    .srow .cnt { font-size: 0.7rem; background: var(--accent-grad); color: #06121a; border-radius: 999px; padding: 0 0.4rem; font-weight: 700; }
    .hint { padding: 0.5rem; font-size: 0.8rem; }
    .conv { display: flex; flex-direction: column; overflow: hidden; }
    .conv-head { display: flex; align-items: center; justify-content: space-between; gap: 0.8rem; padding: 0.7rem 1rem; border-bottom: 1px solid var(--glass-border); }
    .title-in { background: transparent; border: none; font-weight: 700; font-size: 1rem; color: var(--text-1); flex: 1; min-width: 0; }
    .head-right { display: flex; align-items: center; gap: 0.8rem; flex-shrink: 0; }
    .model-of { display: flex; align-items: center; gap: 0.4rem; }
    .approved { font-size: 0.78rem; white-space: nowrap; }
    :host ::ng-deep .ver-sel { font-size: 0.78rem; }
    .stream { flex: 1; overflow: auto; padding: 1rem; display: flex; flex-direction: column; gap: 0.9rem; }
    .msg { display: flex; gap: 0.6rem; max-width: 86%; }
    .msg.user { flex-direction: row-reverse; margin-inline-start: auto; }
    .msg.editing { max-width: 100%; width: 100%; }
    .msg.editing .bubble { flex: 1; }
    .avatar { font-size: 1.3rem; }
    .bubble { padding: 0.7rem 0.9rem; border-radius: 16px; }
    .msg.user .bubble { background: var(--accent-soft); }
    .content { margin: 0; white-space: pre-wrap; line-height: 1.7; }
    /* Markdown-rendered assistant replies (headings + tables the magic wand emits) */
    .content.md { white-space: normal; }
    .content.md :first-child { margin-top: 0; }
    .content.md :last-child { margin-bottom: 0; }
    .content.md h1, .content.md h2, .content.md h3 { line-height: 1.35; margin: 0.8rem 0 0.4rem; font-weight: 700; }
    .content.md h1 { font-size: 1.15rem; }
    .content.md h2 { font-size: 1.05rem; }
    .content.md h3 { font-size: 0.98rem; }
    .content.md p { margin: 0.4rem 0; }
    .content.md ul, .content.md ol { margin: 0.4rem 0; padding-inline-start: 1.4rem; }
    .content.md li { margin: 0.15rem 0; }
    .content.md a { color: var(--accent); }
    .content.md code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.86em; background: var(--glass-bg); padding: 0.1em 0.35em; border-radius: 6px; direction: ltr; unicode-bidi: embed; }
    .content.md pre { background: var(--glass-bg); border: 1px solid var(--glass-border); border-radius: 12px; padding: 0.7rem 0.9rem; overflow: auto; direction: ltr; text-align: left; }
    .content.md pre code { background: none; padding: 0; }
    .content.md blockquote { margin: 0.5rem 0; padding-inline-start: 0.8rem; border-inline-start: 3px solid var(--glass-border); color: var(--text-2); }
    .content.md table { direction: rtl; border-collapse: collapse; width: 100%; margin: 0.6rem 0; font-size: 0.9rem; }
    .content.md th, .content.md td { border: 1px solid var(--glass-border); padding: 0.4rem 0.6rem; text-align: start; }
    .content.md th { background: var(--glass-bg); font-weight: 700; }
    .tags { display: flex; gap: 0.3rem; margin-top: 0.4rem; }
    .msg-actions { display: flex; gap: 0.2rem; margin-top: 0.3rem; flex-wrap: wrap; }
    .composer-in { width: 100%; }
    .edit-head { margin-bottom: 0.5rem; display: flex; gap: 0.4rem; align-items: center; }
    .edit-area { width: 100%; min-height: 260px; font-size: 0.98rem; line-height: 1.8; resize: vertical; }
    .edit-actions { display: flex; gap: 0.5rem; margin-top: 0.6rem; }
    .caret { display: inline-block; margin-inline-start: 2px; color: var(--accent); animation: blink 1s steps(2) infinite; }
    @keyframes blink { 50% { opacity: 0; } }
    .composer { display: flex; gap: 0.5rem; align-items: flex-end; padding: 0.7rem; border-top: 1px solid var(--glass-border); }
    .composer-in { flex: 1; resize: none; }
    .empty { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; gap: 0.4rem; }
    .empty .big { font-size: 2.4rem; }
    @media (max-width: 760px) { .chat-layout { grid-template-columns: 1fr; height: auto; } }
  `],
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
