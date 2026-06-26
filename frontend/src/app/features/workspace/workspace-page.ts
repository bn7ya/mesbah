import { Component, Input, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TabsModule } from 'primeng/tabs';
import { ButtonModule } from 'primeng/button';
import { TagModule } from 'primeng/tag';
import { forkJoin } from 'rxjs';
import { Api } from '../../core/api';
import { ModelVersion, Project } from '../../core/types';
import { ChatPanel } from '../chat/chat-panel';
import { TasksPanel } from '../tasks/tasks-panel';
import { TrainingPanel } from '../training/training-panel';
import { VersionsPanel } from '../versions/versions-panel';
import { AutoEnhancePanel } from '../auto-enhance/auto-enhance-panel';

@Component({
  selector: 'app-workspace-page',
  imports: [
    RouterLink, TabsModule, ButtonModule, TagModule,
    ChatPanel, TasksPanel, TrainingPanel, VersionsPanel, AutoEnhancePanel,
  ],
  template: `
    @if (project(); as p) {
      <section class="page">
        <header class="head glass">
          <a routerLink="/" class="back"><i class="pi pi-arrow-right"></i></a>
          <div class="meta">
            <h1 class="name">{{ p.name }}</h1>
            <div class="row">
              <code class="ltr base">{{ p.base_model_repo }}</code>
              <p-tag [value]="p.kind === 'scratch' ? 'من الصفر' : 'fine-tune'"
                     [severity]="p.kind === 'scratch' ? 'warn' : 'info'" />
              @if (activeLabel()) {
                <p-tag [value]="'نشط: ' + activeLabel()" severity="success" icon="pi pi-bolt" />
              }
              @if (mustTrainFirst()) {
                <p-tag value="غير مُدرَّب بعد — درّبه أولًا" severity="warn" icon="pi pi-exclamation-triangle" />
              }
            </div>
            @if (p.description) { <p class="muted desc">{{ p.description }}</p> }
          </div>
        </header>

        <p-tabs [(value)]="tab" class="tabs">
          <p-tablist>
            <p-tab [value]="0"><i class="pi pi-comments"></i> المحادثات والتصحيح</p-tab>
            <p-tab [value]="1"><i class="pi pi-check-square"></i> المهام</p-tab>
            <p-tab [value]="2">
              <i class="pi pi-bolt"></i> التدريب
              @if (p.kind === 'scratch') { <span class="ltr">from scratch</span> }
              @else { <span class="ltr">QLoRA</span> }
            </p-tab>
            <p-tab [value]="3"><i class="pi pi-sync"></i> التحسين التلقائي</p-tab>
            <p-tab [value]="4"><i class="pi pi-sitemap"></i> شجرة الإصدارات</p-tab>
          </p-tablist>
          <p-tabpanels>
            <p-tabpanel [value]="0">
              @if (mustTrainFirst()) {
                <div class="gate glass">
                  <span class="big">🧬</span>
                  <h3>هذا النموذج مبنيّ من الصفر ولم يُدرَّب بعد</h3>
                  <p class="muted">لا توجد أوزان بعد — درّب النموذج أولًا لتوليد الإصدار الأول، ثم تصبح المحادثة والتصحيح متاحَين.</p>
                  <p-button label="انتقل إلى التدريب" icon="pi pi-bolt" (onClick)="tab = 2" />
                </div>
              } @else {
                <app-chat-panel [projectId]="p.id" />
              }
            </p-tabpanel>
            <p-tabpanel [value]="1"><app-tasks-panel [projectId]="p.id" /></p-tabpanel>
            <p-tabpanel [value]="2"><app-training-panel [projectId]="p.id" (changed)="reload()" /></p-tabpanel>
            <p-tabpanel [value]="3"><app-auto-enhance-panel [projectId]="p.id" (changed)="reload()" /></p-tabpanel>
            <p-tabpanel [value]="4"><app-versions-panel [projectId]="p.id" (changed)="reload()" /></p-tabpanel>
          </p-tabpanels>
        </p-tabs>
      </section>
    } @else {
      <div class="muted center">…جارٍ تحميل المشروع</div>
    }
  `,
  styles: [`
    .page { max-width: 1240px; margin: 0 auto; padding: 0.3rem 0.6rem 2rem; }
    .head { display: flex; gap: 1rem; align-items: flex-start; padding: 1.1rem 1.3rem; margin-bottom: 1rem; }
    .back { color: var(--text-2); font-size: 1.2rem; padding-top: 0.3rem; text-decoration: none; }
    .back:hover { color: var(--text-1); }
    .meta .name { margin: 0 0 0.35rem; font-size: 1.5rem; }
    .row { display: flex; gap: 0.7rem; align-items: center; flex-wrap: wrap; }
    .base { font-size: 0.8rem; color: var(--accent); background: var(--accent-soft); padding: 0.2rem 0.55rem; border-radius: 8px; }
    .desc { margin: 0.5rem 0 0; font-size: 0.88rem; }
    .center { text-align: center; padding: 4rem; }
    .gate { text-align: center; padding: 3rem 2rem; display: flex; flex-direction: column; align-items: center; gap: 0.6rem; }
    .gate .big { font-size: 2.8rem; }
    .gate h3 { margin: 0; }
    .gate p { max-width: 460px; }
    :host ::ng-deep .p-tablist { background: transparent; }
    :host ::ng-deep .p-tabpanels { background: transparent; padding: 1.1rem 0 0; }
    :host ::ng-deep .p-tab { color: var(--text-2); font-weight: 600; }
    :host ::ng-deep .p-tab[data-p-active="true"] { color: var(--accent); }
  `],
})
export class WorkspacePage implements OnInit, OnDestroy {
  @Input() id!: string;                       // bound from route param
  private api = inject(Api);

  readonly project = signal<Project | null>(null);
  readonly versions = signal<ModelVersion[]>([]);
  // PrimeNG Tabs active value (two-way). Defaults to chat (0); for an untrained
  // scratch model we flip to the training tab (2) once the data loads.
  tab = 0;
  private decidedInitialTab = false;

  /** A trained model has at least one non-base version (a real checkpoint). */
  readonly trained = computed(() => this.versions().some((v) => !v.is_base));
  /** A from-scratch project with no weights yet must be trained before chat. */
  readonly mustTrainFirst = computed(
    () => this.project()?.kind === 'scratch' && !this.trained(),
  );

  ngOnInit(): void {
    this.reload();
  }

  ngOnDestroy(): void {
    // Offload the model from VRAM when leaving the project.
    this.api.unloadModel().subscribe({ next: () => {}, error: () => {} });
  }

  reload(): void {
    // Load project + versions together so the initial tab + chat gating are
    // decided from a consistent snapshot (avoids a chat→training flicker).
    forkJoin({
      project: this.api.getProject(this.id),
      versions: this.api.listVersions(this.id),
    }).subscribe(({ project, versions }) => {
      this.project.set(project);
      this.versions.set(versions);
      if (!this.decidedInitialTab) {
        this.decidedInitialTab = true;
        if (this.mustTrainFirst()) {
          this.tab = 2;                        // land on Training for untrained scratch
        } else {
          // Warm-load the active model in the background (local-only) — only when
          // there are real weights to load (skip the random-init base node).
          this.api.warmupModel(this.id).subscribe({ next: () => {}, error: () => {} });
        }
      }
    });
  }

  activeLabel(): string | null {
    const p = this.project();
    const v = this.versions().find((x) => x.id === p?.active_version_id);
    return v ? v.label : null;
  }
}
