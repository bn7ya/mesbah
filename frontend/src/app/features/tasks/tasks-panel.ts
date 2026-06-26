import { Component, Input, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';
import { TextareaModule } from 'primeng/textarea';
import { SelectModule } from 'primeng/select';
import { TagModule } from 'primeng/tag';
import { Api } from '../../core/api';
import { Task, TaskStatus } from '../../core/types';

@Component({
  selector: 'app-tasks-panel',
  imports: [FormsModule, ButtonModule, InputTextModule, TextareaModule, SelectModule, TagModule],
  template: `
    <div class="flex flex-col gap-3">
      <div class="flex flex-wrap items-center gap-2 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-3">
        <input pInputText [(ngModel)]="title" placeholder="عنوان المهمة (ماذا يجب أن يتقنه النموذج؟)" class="flex-1 min-w-[180px]" />
        <input pInputText [(ngModel)]="objective" placeholder="معيار النجاح / objective" class="flex-1 min-w-[180px]" />
        <p-button label="إضافة" icon="pi pi-plus" [disabled]="!title.trim()" (onClick)="add()" />
      </div>

      <div class="flex flex-col gap-2">
        @for (t of tasks(); track t.id) {
          <div class="flex items-center gap-3 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 px-4 py-3">
            <div class="flex-1">
              <h4 class="m-0 text-[0.98rem] font-medium">{{ t.title }}</h4>
              @if (t.objective) { <p class="mt-0.5 mb-0 text-sm text-neutral-500">{{ t.objective }}</p> }
            </div>
            <p-select [options]="statuses" optionLabel="label" optionValue="value"
                      [ngModel]="t.status" (onChange)="setStatus(t, $event.value)" />
            <p-button icon="pi pi-trash" [text]="true" severity="danger" (onClick)="remove(t)" />
          </div>
        }
        @if (tasks().length === 0) {
          <p class="text-center text-neutral-500 py-8">لا مهام بعد. أضف الأهداف التي تريد أن يتعلّمها النموذج.</p>
        }
      </div>
    </div>
  `,
})
export class TasksPanel implements OnInit {
  @Input() projectId!: string;
  private api = inject(Api);
  readonly tasks = signal<Task[]>([]);
  title = '';
  objective = '';
  statuses = [
    { label: 'قيد الانتظار', value: 'todo' as TaskStatus },
    { label: 'قيد التنفيذ', value: 'in_progress' as TaskStatus },
    { label: 'مكتملة', value: 'done' as TaskStatus },
  ];

  ngOnInit(): void { this.load(); }
  load(): void { this.api.listTasks(this.projectId).subscribe((t) => this.tasks.set(t)); }

  add(): void {
    if (!this.title.trim()) return;
    this.api.createTask(this.projectId, { title: this.title.trim(), objective: this.objective.trim() })
      .subscribe(() => { this.title = ''; this.objective = ''; this.load(); });
  }
  setStatus(t: Task, status: TaskStatus): void { this.api.updateTask(this.projectId, t.id, { status }).subscribe(() => this.load()); }
  remove(t: Task): void { this.api.deleteTask(this.projectId, t.id).subscribe(() => this.load()); }
}
