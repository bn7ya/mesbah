import { Component, Input, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TabsModule } from 'primeng/tabs';
import { ButtonModule } from 'primeng/button';
import { TagModule } from 'primeng/tag';
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
              @if (activeLabel()) {
                <p-tag [value]="'نشط: ' + activeLabel()" severity="success" icon="pi pi-bolt" />
              }
            </div>
            @if (p.description) { <p class="muted desc">{{ p.description }}</p> }
          </div>
        </header>

        <p-tabs [value]="0" class="tabs">
          <p-tablist>
            <p-tab [value]="0"><i class="pi pi-comments"></i> المحادثات والتصحيح</p-tab>
            <p-tab [value]="1"><i class="pi pi-check-square"></i> المهام</p-tab>
            <p-tab [value]="2"><i class="pi pi-bolt"></i> التدريب <span class="ltr">QLoRA</span></p-tab>
            <p-tab [value]="3"><i class="pi pi-sync"></i> التحسين التلقائي</p-tab>
            <p-tab [value]="4"><i class="pi pi-sitemap"></i> شجرة الإصدارات</p-tab>
          </p-tablist>
          <p-tabpanels>
            <p-tabpanel [value]="0"><app-chat-panel [projectId]="p.id" /></p-tabpanel>
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

  ngOnInit(): void {
    this.reload();
    // Warm-load the active model on entering the project (background, local-only).
    this.api.warmupModel(this.id).subscribe({ next: () => {}, error: () => {} });
  }

  ngOnDestroy(): void {
    // Offload the model from VRAM when leaving the project.
    this.api.unloadModel().subscribe({ next: () => {}, error: () => {} });
  }

  reload(): void {
    this.api.getProject(this.id).subscribe((p) => this.project.set(p));
    this.api.listVersions(this.id).subscribe((v) => this.versions.set(v));
  }

  activeLabel(): string | null {
    const p = this.project();
    const v = this.versions().find((x) => x.id === p?.active_version_id);
    return v ? v.label : null;
  }
}
