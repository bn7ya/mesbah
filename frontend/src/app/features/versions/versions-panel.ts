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
    <div class="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-5">
      <div class="mb-4">
        <h3 class="m-0 text-base font-semibold">شجرة الإصدارات <span class="text-xs font-normal text-neutral-400">— حسّن، فرّع، أو ارجع لأي إصدار</span></h3>
      </div>

      <div class="flex flex-col gap-2">
        @for (f of flat(); track f.node.id) {
          <div class="flex items-stretch gap-2" [style.padding-inline-start.px]="f.depth * 26">
            <span class="mono pt-2.5 text-neutral-400" [class.text-blue-500]="f.node.is_base">{{ f.node.is_base ? '●' : '├─' }}</span>
            <div class="flex-1 flex items-center justify-between gap-3 rounded-lg border px-3.5 py-2.5 transition-colors"
                 [class]="f.node.is_active
                   ? 'border-blue-400 dark:border-blue-500 ring-1 ring-blue-400/40 bg-blue-50/50 dark:bg-blue-950/20'
                   : 'border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-900'">
              <div>
                <div class="flex items-center gap-2">
                  <span class="font-semibold">{{ f.node.label }}</span>
                  @if (f.node.is_base) { <p-tag value="أساسي" severity="contrast" /> }
                  @if (f.node.is_active) { <p-tag value="نشط" severity="success" icon="pi pi-bolt" /> }
                </div>
                <div class="flex flex-wrap gap-1.5 mt-0.5 text-xs text-neutral-400">
                  <span class="ltr">{{ f.node.created_at | date:'short' }}</span>
                  @if (asNum(f.node.metrics['train_loss']); as l) { <span class="ltr">· loss {{ l | number:'1.4-4' }}</span> }
                  @if (f.node.adapter_path) { <span class="ltr text-emerald-600 dark:text-emerald-400" title="LoRA adapter">· adapter ✓</span> }
                </div>
                @if (f.node.notes) { <p class="mt-1 mb-0 text-xs text-neutral-500">{{ f.node.notes }}</p> }
              </div>
              <div class="flex gap-0.5 shrink-0">
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

      <p class="flex items-start gap-1.5 mt-4 text-xs leading-relaxed text-neutral-500">
        <i class="pi pi-info-circle mt-0.5"></i>
        <span>التدريب يضيف عقدة جديدة أسفل الإصدار النشط. «تفعيل» إصدار أقدم يعني الرجوع <code class="ltr">rollback</code>،
        والتدريب من إصدار وسطي يُنشئ فرعًا جديدًا.</span>
      </p>
    </div>
  `,
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
