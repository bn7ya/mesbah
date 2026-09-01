import { Component, EventEmitter, Input, OnInit, Output, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { SelectModule } from 'primeng/select';
import { ToggleSwitchModule } from 'primeng/toggleswitch';
import { TableModule, TableLazyLoadEvent } from 'primeng/table';
import { TagModule } from 'primeng/tag';
import { Api } from '../../core/api';
import { DataLabExample, DataLabStatus, DataLabSummary, Task } from '../../core/types';

const STATUS_LABEL: Record<DataLabStatus, string> = {
  pending: 'بانتظار المراجعة', approved: 'معتمد ومُدرَج', excluded: 'مستبعد',
};
const STATUS_SEV: Record<DataLabStatus, 'warn' | 'success' | 'secondary'> = {
  pending: 'warn', approved: 'success', excluded: 'secondary',
};

@Component({
  selector: 'app-data-lab-panel',
  imports: [FormsModule, ButtonModule, SelectModule, ToggleSwitchModule, TableModule, TagModule],
  template: `
    <div class="flex flex-col gap-4">
      <p class="text-sm text-neutral-500 m-0">
        كل رد اعتمدته عبر المحادثة يظهر هنا. راجع الأمثلة، وحدّد ما يُدرَج فعليًا في
        جلسة التدريب القادمة قبل أن تبدأها — التغييرات هنا تنعكس مباشرة على عدد
        الأمثلة الجاهزة في تبويب <code class="ltr">التدريب</code>.
      </p>

      <div class="flex flex-wrap gap-3">
        <div class="flex-1 min-w-[140px] rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 px-3 py-2.5">
          <span class="block text-xs text-neutral-500">إجمالي الردود</span>
          <span class="text-lg font-bold ltr">{{ summary()?.total_candidates ?? 0 }}</span>
        </div>
        <div class="flex-1 min-w-[140px] rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 px-3 py-2.5">
          <span class="block text-xs text-neutral-500">معتمد ومُدرَج</span>
          <span class="text-lg font-bold ltr">{{ summary()?.included_count ?? 0 }}</span>
        </div>
        <div class="flex-1 min-w-[160px] rounded-lg border border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-950/30 px-3 py-2.5">
          <span class="block text-xs text-blue-700 dark:text-blue-300">سيُستخدم في التدريب القادم</span>
          <span class="text-lg font-bold ltr text-blue-700 dark:text-blue-300">{{ summary()?.would_include_count ?? 0 }}</span>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-2 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-3">
        <p-select [options]="statusOptions" optionLabel="label" optionValue="value"
                  [(ngModel)]="statusFilter" (onChange)="reload()" placeholder="الحالة" styleClass="min-w-[180px]" />
        <p-select [options]="taskOptions()" optionLabel="label" optionValue="value"
                  [(ngModel)]="taskFilter" (onChange)="reload()" placeholder="كل المهام" styleClass="min-w-[180px]" />
        <label class="flex items-center gap-2 text-sm cursor-pointer ms-auto">
          <p-toggleswitch [(ngModel)]="onlyCorrected" (onChange)="reload()" />
          الأمثلة المُصحّحة فقط
        </label>
      </div>

      @if (selection.length > 0) {
        <div class="flex flex-wrap items-center gap-2 rounded-lg border border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-950/30 px-3 py-2">
          <span class="text-sm text-blue-700 dark:text-blue-300">{{ selection.length }} محدّد</span>
          <p-button label="اعتماد وتضمين" icon="pi pi-check" size="small" (onClick)="approveSelected()" />
          <p-button label="تضمين" icon="pi pi-plus-circle" size="small" [outlined]="true" (onClick)="includeSelected()" />
          <p-button label="استبعاد" icon="pi pi-minus-circle" size="small" severity="danger" [outlined]="true" (onClick)="excludeSelected()" />
          <button class="text-xs text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200 ms-auto" type="button" (click)="selection = []">إلغاء التحديد</button>
        </div>
      }

      <p-table [value]="items()" [(selection)]="selection" dataKey="id"
               [lazy]="true" (onLazyLoad)="onLazyLoad($event)"
               [paginator]="true" [rows]="pageSize" [totalRecords]="total()"
               [loading]="loading()" [rowsPerPageOptions]="[10, 20, 50]"
               styleClass="rounded-lg border border-neutral-200 dark:border-neutral-800 overflow-hidden">
        <ng-template pTemplate="header">
          <tr>
            <th style="width: 3rem"><p-tableHeaderCheckbox /></th>
            <th>المحادثة</th>
            <th style="width: 10rem">المهمة / الجلسة</th>
            <th style="width: 8rem">الحالة</th>
            <th style="width: 6rem">مُدرَج</th>
            <th style="width: 6rem"></th>
          </tr>
        </ng-template>
        <ng-template pTemplate="body" let-ex>
          <tr [class.opacity-50]="!ex.would_include">
            <td><p-tableCheckbox [value]="ex" /></td>
            <td>
              <div class="flex flex-col gap-1 max-w-lg">
                <span class="text-xs text-neutral-400 truncate">{{ ex.user_content || '—' }}</span>
                <span class="text-sm truncate">{{ ex.assistant_content }}</span>
              </div>
            </td>
            <td>
              <div class="flex flex-col gap-0.5 text-xs text-neutral-500">
                <span>{{ ex.task_title || 'بلا مهمة' }}</span>
                <span class="truncate">{{ ex.session_title }}</span>
              </div>
            </td>
            <td>
              <div class="flex flex-col gap-1 items-start">
                <p-tag [value]="statusLabel(ex.status)" [severity]="statusSev(ex.status)" />
                @if (ex.corrected) { <span class="text-[0.68rem] text-neutral-400">مُصحَّح</span> }
              </div>
            </td>
            <td>
              <p-toggleswitch [ngModel]="ex.include_in_training" [disabled]="!ex.approved"
                              (onChange)="toggleInclude(ex)" />
            </td>
            <td>
              @if (ex.status === 'pending') {
                <p-button label="اعتماد" size="small" [text]="true" (onClick)="approveRow(ex)" />
              }
            </td>
          </tr>
        </ng-template>
        <ng-template pTemplate="emptymessage">
          <tr><td colspan="6" class="text-center text-neutral-400 py-8">لا توجد ردود مطابقة لهذا الفلتر بعد.</td></tr>
        </ng-template>
      </p-table>
    </div>
  `,
})
export class DataLabPanel implements OnInit {
  @Input() projectId!: string;
  @Output() changed = new EventEmitter<void>();
  private api = inject(Api);

  readonly items = signal<DataLabExample[]>([]);
  readonly total = signal(0);
  readonly summary = signal<DataLabSummary | null>(null);
  readonly loading = signal(false);
  readonly taskOptions = signal<{ label: string; value: string | null }[]>([{ label: 'كل المهام', value: null }]);

  statusOptions = [
    { label: 'كل الحالات', value: null },
    { label: STATUS_LABEL['pending'], value: 'pending' as DataLabStatus },
    { label: STATUS_LABEL['approved'], value: 'approved' as DataLabStatus },
    { label: STATUS_LABEL['excluded'], value: 'excluded' as DataLabStatus },
  ];
  statusFilter: DataLabStatus | null = null;
  taskFilter: string | null = null;
  onlyCorrected = false;
  selection: DataLabExample[] = [];
  page = 1;
  pageSize = 10;

  ngOnInit(): void {
    this.api.listTasks(this.projectId).subscribe((tasks: Task[]) => {
      this.taskOptions.set([{ label: 'كل المهام', value: null }, ...tasks.map((t) => ({ label: t.title, value: t.id }))]);
    });
    this.reload();
  }

  reload(): void {
    this.page = 1;
    this.selection = [];
    this.load();
  }

  onLazyLoad(event: TableLazyLoadEvent): void {
    this.pageSize = event.rows || this.pageSize;
    this.page = Math.floor((event.first || 0) / this.pageSize) + 1;
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.api.dataLabExamples(this.projectId, {
      task_id: this.taskFilter ?? undefined,
      status: this.statusFilter ?? undefined,
      only_corrected: this.onlyCorrected || undefined,
      page: this.page,
      page_size: this.pageSize,
    }).subscribe({
      next: (r) => { this.items.set(r.items); this.total.set(r.total); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
    this.api.dataLabSummary(this.projectId, {
      task_id: this.taskFilter ?? undefined,
      only_corrected: this.onlyCorrected || undefined,
    }).subscribe((s) => this.summary.set(s));
  }

  statusLabel(s: DataLabStatus): string { return STATUS_LABEL[s]; }
  statusSev(s: DataLabStatus) { return STATUS_SEV[s]; }

  private bulkSet(ids: string[], approved?: boolean, include_in_training?: boolean): void {
    if (!ids.length) return;
    this.api.dataLabBulkUpdate(this.projectId, { message_ids: ids, approved, include_in_training }).subscribe(() => {
      this.selection = [];
      this.load();
      this.changed.emit();
    });
  }
  includeSelected(): void { this.bulkSet(this.selection.map((x) => x.id), undefined, true); }
  excludeSelected(): void { this.bulkSet(this.selection.map((x) => x.id), undefined, false); }
  approveSelected(): void { this.bulkSet(this.selection.map((x) => x.id), true, true); }
  toggleInclude(ex: DataLabExample): void { this.bulkSet([ex.id], undefined, !ex.include_in_training); }
  approveRow(ex: DataLabExample): void { this.bulkSet([ex.id], true, true); }
}
