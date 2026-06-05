import { Component, Input, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { TextareaModule } from 'primeng/textarea';
import { TagModule } from 'primeng/tag';
import { TooltipModule } from 'primeng/tooltip';
import { MessageService } from 'primeng/api';
import { Api } from '../../core/api';
import { ChatMessage, ChatSession } from '../../core/types';

@Component({
  selector: 'app-chat-panel',
  imports: [FormsModule, ButtonModule, InputTextModule, TextareaModule, TagModule, TooltipModule],
  template: `
    <div class="chat-layout">
      <!-- sessions rail -->
      <aside class="rail glass">
        <div class="rail-head">
          <span class="t">الجلسات</span>
          <p-button icon="pi pi-plus" [rounded]="true" [text]="true" size="small" pTooltip="جلسة جديدة" (onClick)="newSession()" />
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
            <span class="muted dim approved"><i class="pi pi-database"></i> {{ s.approved_count }} مثال تدريب</span>
          </header>

          <div class="stream">
            @for (m of s.messages; track m.id) {
              <div class="msg" [class.user]="m.role === 'user'" [class.assistant]="m.role === 'assistant'">
                <div class="avatar">{{ m.role === 'user' ? '🧑' : '🕯️' }}</div>
                <div class="bubble glass">
                  @if (editingId() === m.id) {
                    <textarea pTextarea rows="5" [(ngModel)]="editText" class="edit-area"></textarea>
                    <div class="edit-actions">
                      <p-button label="حفظ التصحيح" icon="pi pi-check" size="small" (onClick)="saveEdit(m)" />
                      <p-button label="إلغاء" severity="secondary" [text]="true" size="small" (onClick)="editingId.set(null)" />
                    </div>
                  } @else {
                    <p class="content">{{ m.content }}</p>
                    <div class="tags">
                      @if (m.corrected) { <p-tag value="معدّل" severity="warn" icon="pi pi-pencil" /> }
                      @if (m.approved) { <p-tag value="معتمد للتدريب" severity="success" icon="pi pi-check" /> }
                    </div>
                    @if (m.role === 'assistant') {
                      <div class="msg-actions">
                        <p-button icon="pi pi-pencil" [text]="true" size="small" label="تصحيح" (onClick)="startEdit(m)" />
                        <p-button [icon]="m.approved ? 'pi pi-star-fill' : 'pi pi-star'" [text]="true" size="small"
                                  [label]="m.approved ? 'إلغاء الاعتماد' : 'اعتماد'" (onClick)="toggleApprove(m)" />
                        @if (isLast(m)) {
                          <p-button icon="pi pi-refresh" [text]="true" size="small" label="إعادة توليد" (onClick)="regenerate()" />
                        }
                      </div>
                    }
                  }
                </div>
              </div>
            }
            @if (thinking()) {
              <div class="msg assistant"><div class="avatar">🕯️</div><div class="bubble glass thinking">…النموذج يكتب</div></div>
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
  `,
  styles: [`
    .chat-layout { display: grid; grid-template-columns: 260px 1fr; gap: 0.9rem; height: 68vh; }
    .rail { padding: 0.8rem; display: flex; flex-direction: column; }
    .rail-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
    .rail-head .t { font-weight: 700; }
    .sessions { display: flex; flex-direction: column; gap: 0.3rem; overflow: auto; }
    .srow { display: flex; align-items: center; gap: 0.5rem; padding: 0.55rem 0.6rem; border-radius: 10px; background: transparent; border: 1px solid transparent; color: var(--text-2); cursor: pointer; text-align: start; }
    .srow:hover { background: var(--glass-bg); color: var(--text-1); }
    .srow.sel { background: var(--glass-bg-strong); color: var(--text-1); border-color: var(--glass-border); }
    .srow .st { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 0.86rem; }
    .srow .cnt { font-size: 0.7rem; background: var(--accent-grad); color: #06121a; border-radius: 999px; padding: 0 0.4rem; font-weight: 700; }
    .hint { padding: 0.5rem; font-size: 0.8rem; }
    .conv { display: flex; flex-direction: column; overflow: hidden; }
    .conv-head { display: flex; align-items: center; justify-content: space-between; padding: 0.7rem 1rem; border-bottom: 1px solid var(--glass-border); }
    .title-in { background: transparent; border: none; font-weight: 700; font-size: 1rem; color: var(--text-1); }
    .approved { font-size: 0.78rem; }
    .stream { flex: 1; overflow: auto; padding: 1rem; display: flex; flex-direction: column; gap: 0.9rem; }
    .msg { display: flex; gap: 0.6rem; max-width: 86%; }
    .msg.user { flex-direction: row-reverse; margin-inline-start: auto; }
    .avatar { font-size: 1.3rem; }
    .bubble { padding: 0.7rem 0.9rem; border-radius: 16px; }
    .msg.user .bubble { background: rgba(79,209,197,0.12); }
    .content { margin: 0; white-space: pre-wrap; line-height: 1.7; }
    .tags { display: flex; gap: 0.3rem; margin-top: 0.4rem; }
    .msg-actions { display: flex; gap: 0.2rem; margin-top: 0.3rem; flex-wrap: wrap; }
    .edit-area, .composer-in { width: 100%; }
    .edit-actions { display: flex; gap: 0.4rem; margin-top: 0.4rem; }
    .thinking { color: var(--text-2); font-style: italic; }
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
  draft = '';
  editText = '';

  ngOnInit(): void { this.loadSessions(); }

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

  send(): void {
    const s = this.current();
    if (!s || !this.draft.trim()) return;
    const text = this.draft.trim();
    this.draft = '';
    this.thinking.set(true);
    this.api.chat(s.id, text).subscribe({
      next: (msgs) => { this.thinking.set(false); this.append(msgs); this.refreshList(); },
      error: (e) => {
        this.thinking.set(false);
        this.toast.add({ severity: e.status === 503 ? 'warn' : 'error', summary: 'تعذر التوليد',
          detail: e.status === 503 ? 'لم يتم تثبيت بيئة النموذج بعد (راجع requirements-ml.txt).' : String(e?.error?.detail ?? e.message), life: 6000 });
        // keep the user's message visible by reloading the session
        this.open(s.id);
      },
    });
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

  startEdit(m: ChatMessage): void { this.editingId.set(m.id); this.editText = m.content; }

  saveEdit(m: ChatMessage): void {
    this.api.editMessage(m.id, { content: this.editText }).subscribe((upd) => {
      this.editingId.set(null);
      this.replace(upd);
      this.refreshList();
      this.toast.add({ severity: 'success', summary: 'حُفظ التصحيح', detail: 'أصبح هذا الرد مثال تدريب معتمد.' });
    });
  }

  toggleApprove(m: ChatMessage): void {
    this.api.editMessage(m.id, { approved: !m.approved }).subscribe((upd) => { this.replace(upd); this.refreshList(); });
  }

  isLast(m: ChatMessage): boolean {
    const msgs = this.current()?.messages ?? [];
    return msgs.length > 0 && msgs[msgs.length - 1].id === m.id;
  }

  private append(msgs: ChatMessage[]): void {
    const s = this.current(); if (!s) return;
    this.current.set({ ...s, messages: [...s.messages, ...msgs] });
  }
  private replace(upd: ChatMessage): void {
    const s = this.current(); if (!s) return;
    this.current.set({ ...s, messages: s.messages.map((x) => (x.id === upd.id ? upd : x)) });
  }
  private refreshList(): void {
    this.api.listSessions(this.projectId).subscribe((s) => this.sessions.set(s));
  }
}
