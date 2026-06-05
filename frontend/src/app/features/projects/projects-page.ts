import { Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { DialogModule } from 'primeng/dialog';
import { InputTextModule } from 'primeng/inputtext';
import { TextareaModule } from 'primeng/textarea';
import { TagModule } from 'primeng/tag';
import { MessageService } from 'primeng/api';
import { Api } from '../../core/api';
import { CuratedModel, Project } from '../../core/types';

@Component({
  selector: 'app-projects-page',
  imports: [
    DatePipe, FormsModule, RouterLink, ButtonModule, DialogModule,
    InputTextModule, TextareaModule, TagModule,
  ],
  template: `
    <section class="page">
      <div class="head">
        <div>
          <h1 class="title">المشاريع</h1>
          <p class="muted sub">كل مشروع يأخذ نموذجًا أساسيًا <code class="ltr">base model</code> ويضبطه عبر الجلسات والمهام.</p>
        </div>
        <p-button label="مشروع جديد" icon="pi pi-plus" (onClick)="openNew()" />
      </div>

      @if (loading()) {
        <div class="muted center">…جارٍ التحميل</div>
      } @else if (projects().length === 0) {
        <div class="empty glass">
          <span class="big">🕯️</span>
          <h3>لا توجد مشاريع بعد</h3>
          <p class="muted">ابدأ بإنشاء مشروع واختيار النموذج الأساسي المناسب للعربية.</p>
          <p-button label="أنشئ أول مشروع" icon="pi pi-plus" (onClick)="openNew()" />
        </div>
      } @else {
        <div class="grid">
          @for (p of projects(); track p.id) {
            <a class="card glass" [routerLink]="['/projects', p.id]">
              <div class="card-top">
                <h3 class="name">{{ p.name }}</h3>
                <p-tag [value]="p.language" severity="contrast" styleClass="lang" />
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

    <p-dialog header="مشروع جديد" [(visible)]="dialog" [modal]="true" [style]="{ width: '780px', maxWidth: '94vw' }" [dismissableMask]="true">
      <div class="form">
        <label class="lbl">اسم المشروع</label>
        <input pInputText [(ngModel)]="form.name" placeholder="مثال: مساعد خدمة العملاء بالعربية" />

        <label class="lbl">الوصف <span class="dim">(اختياري)</span></label>
        <textarea pTextarea rows="2" [(ngModel)]="form.description" placeholder="ماذا سيتعلم هذا النموذج؟"></textarea>

        <label class="lbl">النموذج الأساسي <code class="ltr">base model</code></label>
        <div class="models">
          @for (m of models(); track m.repo_id) {
            <button class="model glass" [class.sel]="form.base_model_repo === m.repo_id"
                    (click)="selectCard(m.repo_id)" type="button">
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
        <div class="custom">
          <label class="lbl">أو معرّف نموذج مخصص من <code class="ltr">HuggingFace</code></label>
          <input pInputText class="ltr" [ngModel]="customRepo()" (ngModelChange)="setCustom($event)"
                 placeholder="مثال: Qwen/Qwen3-8B  ·  ابحث وحمّل من صفحة النماذج" />
        </div>
      </div>
      <ng-template pTemplate="footer">
        <p-button label="إلغاء" severity="secondary" [text]="true" (onClick)="dialog.set(false)" />
        <p-button label="إنشاء المشروع" icon="pi pi-check" [disabled]="!canCreate()" [loading]="creating()" (onClick)="create()" />
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
    .form { display: flex; flex-direction: column; gap: 0.55rem; }
    .lbl { font-weight: 600; margin-top: 0.5rem; }
    .models { display: grid; grid-template-columns: 1fr 1fr; gap: 0.7rem; margin-top: 0.3rem; }
    .model { text-align: start; padding: 0.85rem; cursor: pointer; border: 1px solid var(--glass-border); display: flex; flex-direction: column; gap: 0.4rem; transition: all 0.15s ease; }
    .model:hover { border-color: var(--accent); }
    .model.sel { border-color: var(--accent); box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 40%, transparent); }
    .model-head { display: flex; justify-content: space-between; align-items: center; }
    .model .repo { font-weight: 700; font-size: 0.86rem; }
    .badges { display: flex; flex-wrap: wrap; gap: 0.3rem; }
    .badges .b { font-size: 0.68rem; padding: 0.12rem 0.45rem; border-radius: 6px; background: rgba(150,95,70,0.09); }
    .model .note { font-size: 0.74rem; margin: 0; }
    @media (max-width: 640px) { .models { grid-template-columns: 1fr; } }
  `],
})
export class ProjectsPage implements OnInit {
  private api = inject(Api);
  private router = inject(Router);
  private toast = inject(MessageService);

  readonly projects = signal<Project[]>([]);
  readonly models = signal<CuratedModel[]>([]);
  readonly loading = signal(true);
  readonly dialog = signal(false);
  readonly creating = signal(false);
  readonly customRepo = signal('');
  form = { name: '', description: '', base_model_repo: '' };

  setCustom(v: string): void {
    this.customRepo.set(v);
    if (v.trim()) this.form.base_model_repo = v.trim();   // free-text overrides card selection
  }
  selectCard(repo: string): void { this.form.base_model_repo = repo; this.customRepo.set(''); }

  ngOnInit(): void {
    this.api.listProjects().subscribe({
      next: (p) => { this.projects.set(p); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
    this.api.curatedModels().subscribe((m) => this.models.set(m));
  }

  openNew(): void {
    this.customRepo.set('');
    this.form = { name: '', description: '', base_model_repo: this.models().find((m) => m.recommended)?.repo_id ?? '' };
    this.dialog.set(true);
  }

  canCreate(): boolean { return !!this.form.name.trim() && !!this.form.base_model_repo; }

  create(): void {
    if (!this.canCreate()) return;
    this.creating.set(true);
    this.api.createProject(this.form).subscribe({
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
}
