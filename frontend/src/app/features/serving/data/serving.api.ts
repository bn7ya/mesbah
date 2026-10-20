import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { map, type Observable } from 'rxjs';

import type { Page, PageQuery } from '@core/http/api.types';
import {
  ENGINES_PAGE_SIZE,
  EXAMPLE_PROJECTS,
  type ApiKey,
  type CreatedApiKey,
  type Engine,
  type EngineChange,
  type NewEngine,
  type ProjectSlugWire,
} from './serving.types';

@Injectable({ providedIn: 'root' })
export class ServingApi {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/serving';

  engines(): Observable<Page<Engine>> {
    const params = new HttpParams({ fromObject: { page_size: ENGINES_PAGE_SIZE } });
    return this.http.get<Page<Engine>>(`${this.base}/engines/`, { params });
  }

  connect(engine: NewEngine): Observable<Engine> {
    return this.http.post<Engine>(`${this.base}/engines/`, engine);
  }

  change(id: string, change: EngineChange): Observable<Engine> {
    return this.http.patch<Engine>(`${this.base}/engines/${id}/`, change);
  }

  disconnect(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/engines/${id}/`);
  }

  unload(id: string): Observable<Engine> {
    return this.http.post<Engine>(`${this.base}/engines/${id}/unload/`, null);
  }

  keys(query: PageQuery): Observable<Page<ApiKey>> {
    const params = new HttpParams({ fromObject: { ...query } });
    return this.http.get<Page<ApiKey>>(`${this.base}/keys/`, { params });
  }

  createKey(name: string): Observable<CreatedApiKey> {
    return this.http.post<CreatedApiKey>(`${this.base}/keys/`, { name });
  }

  revokeKey(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/keys/${id}/`);
  }

  exampleSlugs(): Observable<readonly string[]> {
    const params = new HttpParams({ fromObject: { page_size: EXAMPLE_PROJECTS } });
    return this.http
      .get<Page<ProjectSlugWire>>('/api/projects/', { params })
      .pipe(map((page) => page.results.map((project) => project.slug)));
  }
}
