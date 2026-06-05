import { Component, EventEmitter, Input, OnInit, Output, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { ButtonModule } from 'primeng/button';
import { TagModule } from 'primeng/tag';
import { ConfirmationService, MessageService } from 'primeng/api';
import { Api } from '../../core/api';
import { VersionNode } from '../../core/types';

interface FlatNode { node: VersionNode; depth: number; isLastChild: boolean; }

@Component({
  selector: 'app-versions-panel',
  imports: [DatePipe, DecimalPipe, ButtonModule, TagModule],
  template: `
    <div class="wrap glass">
      <div class="head">
        <h3 class="h">شجرة الإصدارات <span class="muted dim small">— حسّن، فرّع، أو ارجع لأي إصدار</span></h3>
      </div>

      <div class="tree">
        @for (f of flat(); track f.node.id) {
          <div class="node" [style.padding-inline-start.px]="f.depth * 26">
            <span class="rail" [class.root]="f.node.is_base">{{ f.node.is_base ? '●' : '├─' }}</span>
            <div class="node-card" [class.active]="f.node.is_active" [class.base]="f.node.is_base">
              <div class="node-main">
                <div class="line1">
                  <span class="label">{{ f.node.label }}</span>
                  @if (f.node.is_base) { <p-tag value="أساسي" severity="contrast" /> }
                  @if (f.node.is_active) { <p-tag value="نشط" severity="success" icon="pi pi-bolt" /> }
                </div>
                <div class="line2 muted dim small">
                  <span class="ltr">{{ f.node.created_at | date:'short' }}</span>
                  @if (asNum(f.node.metrics['train_loss']); as l) { <span class="ltr">· loss {{ l | number:'1.4-4' }}</span> }
                  @if (f.node.adapter_path) { <span class="ltr adapter" title="LoRA adapter">· adapter ✓</span> }
                </div>
                @if (f.node.notes) { <p class="notes muted small">{{ f.node.notes }}</p> }
              </div>
              <div class="node-actions">
                @if (!f.node.is_active) {
                  <p-button icon="pi pi-bolt" [text]="true" size="small" label="تفعيل" (onClick)="activate(f.node)" />
                }
                @if (!f.node.is_base) {
                  <p-button icon="pi pi-trash" [text]="true" severity="danger" size="small" (onClick)="remove(f.node)" />
                }
              </div>
            </div>
          </div>
        }
      </div>

      <p class="hint muted small">
        <i class="pi pi-info-circle"></i>
        التدريب يضيف عقدة جديدة أسفل الإصدار النشط. «تفعيل» إصدار أقدم يعني الرجوع <code class="ltr">rollback</code>،
        والتدريب من إصدار وسطي يُنشئ فرعًا جديدًا.
      </p>
    </div>
  `,
  styles: [`
    .wrap { padding: 1.1rem 1.2rem; }
    .head { margin-bottom: 0.9rem; }
    .h { margin: 0; font-size: 1.1rem; }
    .small { font-size: 0.74rem; }
    .tree { display: flex; flex-direction: column; gap: 0.5rem; }
    .node { display: flex; align-items: stretch; gap: 0.4rem; }
    .rail { color: var(--text-3); font-family: var(--font-mono); padding-top: 0.7rem; }
    .rail.root { color: var(--accent); }
    .node-card { flex: 1; display: flex; justify-content: space-between; gap: 0.8rem; align-items: center; padding: 0.7rem 0.9rem; border-radius: 14px; background: var(--glass-bg); border: 1px solid var(--glass-border); transition: all 0.15s ease; }
    .node-card.active { border-color: var(--accent); box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 40%, transparent); }
    .node-card.base { background: rgba(255,255,255,0.04); }
    .line1 { display: flex; align-items: center; gap: 0.5rem; }
    .label { font-weight: 700; }
    .line2 { display: flex; gap: 0.5rem; margin-top: 0.2rem; flex-wrap: wrap; }
    .adapter { color: var(--ok); }
    .notes { margin: 0.3rem 0 0; }
    .node-actions { display: flex; gap: 0.2rem; }
    .hint { margin-top: 1rem; display: flex; gap: 0.4rem; align-items: flex-start; line-height: 1.6; }
  `],
})
export class VersionsPanel implements OnInit {
  @Input() projectId!: string;
  @Output() changed = new EventEmitter<void>();
  private api = inject(Api);
  private confirm = inject(ConfirmationService);
  private toast = inject(MessageService);

  readonly flat = signal<FlatNode[]>([]);

  ngOnInit(): void { this.load(); }

  load(): void {
    this.api.versionTree(this.projectId).subscribe((roots) => {
      const out: FlatNode[] = [];
      const walk = (n: VersionNode, depth: number, last: boolean) => {
        out.push({ node: n, depth, isLastChild: last });
        n.children?.forEach((c, i) => walk(c, depth + 1, i === n.children.length - 1));
      };
      roots.forEach((r, i) => walk(r, 0, i === roots.length - 1));
      this.flat.set(out);
    });
  }

  activate(n: VersionNode): void {
    this.api.activateVersion(this.projectId, n.id).subscribe(() => {
      this.toast.add({ severity: 'success', summary: 'تم التفعيل', detail: n.label });
      this.load();
      this.changed.emit();
    });
  }

  remove(n: VersionNode): void {
    this.confirm.confirm({
      header: 'حذف الإصدار',
      message: `حذف «${n.label}»؟ سيُعاد ربط فروعه بالإصدار الأب.`,
      acceptLabel: 'حذف', rejectLabel: 'إلغاء', acceptButtonStyleClass: 'p-button-danger',
      accept: () => {
        this.api.deleteVersion(n.id).subscribe(() => { this.load(); this.changed.emit(); });
      },
    });
  }

  asNum(v: unknown): number | null { return typeof v === 'number' ? v : null; }
}
