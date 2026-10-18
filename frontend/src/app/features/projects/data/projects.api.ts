import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { map, type Observable } from 'rxjs';

import type { Page, PageQuery } from '@core/http/api.types';
import {
  READY,
  type LibraryModelWire,
  type ModelOption,
  type NewProject,
  type Project,
  type ProjectChange,
} from './projects.types';

const LIBRARY_PAGE_SIZE = 200;

@Injectable({ providedIn: 'root' })
export class ProjectsApi {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/projects';

  list(query: PageQuery): Observable<Page<Project>> {
    const params = new HttpParams({ fromObject: { ...query } });
    return this.http.get<Page<Project>>(`${this.base}/`, { params });
  }

  find(id: string): Observable<Project> {
    return this.http.get<Project>(`${this.base}/${id}/`);
  }

  create(project: NewProject): Observable<Project> {
    return this.http.post<Project>(`${this.base}/`, project);
  }

  change(id: string, change: ProjectChange): Observable<Project> {
    return this.http.patch<Project>(`${this.base}/${id}/`, change);
  }

  remove(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}/`);
  }

  readyModels(): Observable<readonly ModelOption[]> {
    const params = new HttpParams({ fromObject: { page_size: LIBRARY_PAGE_SIZE } });
    return this.http.get<Page<LibraryModelWire>>('/api/models/', { params }).pipe(
      map((page) =>
        page.results
          .filter((model) => model.status === READY)
          .map(({ id, repo_id, parameters, supports_thinking }) => ({ id, repo_id, parameters, supports_thinking })),
      ),
    );
  }
}
