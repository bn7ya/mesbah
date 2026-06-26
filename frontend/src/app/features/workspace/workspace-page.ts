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
      <section class="max-w-6xl mx-auto px-4 pt-2 pb-8">
        <header class="flex gap-4 items-start mb-5">
          <a routerLink="/" class="text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 text-xl pt-1 no-underline"><i class="pi pi-arrow-right"></i></a>
          <div class="flex-1">
            <h1 class="m-0 mb-1.5 text-2xl font-semibold">{{ p.name }}</h1>
            <div class="flex gap-2 items-center flex-wrap">
              <code class="ltr text-xs text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40 px-2 py-0.5 rounded">{{ p.base_model_repo }}</code>
              <p-tag [value]="p.kind === 'scratch' ? 'من الصفر' : 'fine-tune'"
                     [severity]="p.kind === 'scratch' ? 'warn' : 'info'" />
              @if (activeLabel()) {
                <p-tag [value]="'نشط: ' + activeLabel()" severity="success" icon="pi pi-bolt" />
              }
              @if (mustTrainFirst()) {
                <p-tag value="غير مُدرَّب بعد — درّبه أولًا" severity="warn" icon="pi pi-exclamation-triangle" />
              }
            </div>
            @if (p.description) { <p class="mt-2 mb-0 text-sm text-neutral-500">{{ p.description }}</p> }
          </div>
        </header>

        <p-tabs [(value)]="tab">
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
          <p-tabpanels class="!bg-transparent !px-0">
            <p-tabpanel [value]="0">
              @if (mustTrainFirst()) {
                <div class="flex flex-col items-center gap-2 text-center rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 px-8 py-12">
                  <span class="text-5xl">🧬</span>
                  <h3 class="m-0 text-lg font-semibold">هذا النموذج مبنيّ من الصفر ولم يُدرَّب بعد</h3>
                  <p class="text-neutral-500 max-w-md">لا توجد أوزان بعد — درّب النموذج أولًا لتوليد الإصدار الأول، ثم تصبح المحادثة والتصحيح متاحَين.</p>
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
      <div class="text-center text-neutral-500 py-16">…جارٍ تحميل المشروع</div>
    }
  `,
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
