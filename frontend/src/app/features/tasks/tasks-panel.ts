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
    <div class="wrap">
      <div class="new glass">
        <input pInputText [(ngModel)]="title" placeholder="عنوان المهمة (ماذا يجب أن يتقنه النموذج؟)" class="grow" />
        <input pInputText [(ngModel)]="objective" placeholder="معيار النجاح / objective" class="grow" />
        <p-button label="إضافة" icon="pi pi-plus" [disabled]="!title.trim()" (onClick)="add()" />
      </div>

      <div class="list">
        @for (t of tasks(); track t.id) {
          <div class="task glass">
            <div class="main">
              <h4 class="t">{{ t.title }}</h4>
              @if (t.objective) { <p class="muted obj">{{ t.objective }}</p> }
            </div>
            <p-select [options]="statuses" optionLabel="label" optionValue="value"
                      [ngModel]="t.status" (onChange)="setStatus(t, $event.value)" styleClass="st-sel" />
            <p-button icon="pi pi-trash" [text]="true" severity="danger" (onClick)="remove(t)" />
          </div>
        }
        @if (tasks().length === 0) {
          <p class="muted center">لا مهام بعد. أضف الأهداف التي تريد أن يتعلّمها النموذج.</p>
        }
      </div>
    </div>
  `,
  styles: [`
    .wrap { display: flex; flex-direction: column; gap: 0.9rem; }
    .new { display: flex; gap: 0.5rem; padding: 0.7rem; align-items: center; flex-wrap: wrap; }
    .grow { flex: 1; min-width: 180px; }
    .list { display: flex; flex-direction: column; gap: 0.5rem; }
    .task { display: flex; align-items: center; gap: 0.8rem; padding: 0.8rem 1rem; }
    .task .main { flex: 1; }
    .task .t { margin: 0; font-size: 0.98rem; }
    .task .obj { margin: 0.2rem 0 0; font-size: 0.82rem; }
    .center { text-align: center; padding: 2rem; }
  `],
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
