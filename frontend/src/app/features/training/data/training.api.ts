import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { catchError, forkJoin, map, of, type Observable } from 'rxjs';

import type { Page } from '@core/http/api.types';
import {
  DATASETS_PAGE_SIZE,
  METRICS_PAGE_SIZE,
  VERSIONS_PAGE_SIZE,
  type DatasetWire,
  type Draft,
  type Example,
  type LibraryDataset,
  type Metric,
  type NewRun,
  type Plan,
  type ProjectNameWire,
  type Run,
  type SourceNames,
  type StartVersion,
  type VersionSize,
  type VersionWire,
} from './training.types';

@Injectable({ providedIn: 'root' })
export class TrainingApi {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/training';

  runs(project: string, page: number, pageSize: number): Observable<Page<Run>> {
    const params = new HttpParams({ fromObject: { project, page, page_size: pageSize } });
    return this.http.get<Page<Run>>(`${this.base}/`, { params });
  }

  run(id: string): Observable<Run> {
    return this.http.get<Run>(`${this.base}/${id}/`);
  }

  start(project: string, draft: Draft): Observable<Run> {
    const { max_steps, ...settings } = draft.settings;
    const body: NewRun = {
      project,
      starts_from: draft.startsFrom,
      name: draft.name.trim(),
      use_corrections: draft.useCorrections,
      datasets: draft.datasets.map((choice) => ({ id: choice.id, max_rows: choice.maxRows })),
      activate_when_done: draft.activateWhenDone,
      hyperparams: max_steps === null ? settings : { ...settings, max_steps },
    };
    return this.http.post<Run>(`${this.base}/`, body);
  }

  cancel(id: string): Observable<Run> {
    return this.http.post<Run>(`${this.base}/${id}/cancel/`, null);
  }

  remove(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}/`);
  }

  plan(project: string): Observable<Plan> {
    const params = new HttpParams({ fromObject: { project } });
    return this.http.get<Plan>(`${this.base}/plan/`, { params });
  }

  examples(project: string, page: number, pageSize: number): Observable<Page<Example>> {
    const params = new HttpParams({ fromObject: { project, page, page_size: pageSize } });
    return this.http.get<Page<Example>>(`${this.base}/examples/`, { params });
  }

  metrics(id: string, afterStep: number, page: number): Observable<Page<Metric>> {
    const params = new HttpParams({
      fromObject: { after_step: afterStep, page, page_size: METRICS_PAGE_SIZE },
    });
    return this.http.get<Page<Metric>>(`${this.base}/${id}/metrics/`, { params });
  }

  versions(project: string, page: number): Observable<Page<StartVersion>> {
    const params = new HttpParams({ fromObject: { project, page, page_size: VERSIONS_PAGE_SIZE } });
    return this.http.get<Page<VersionWire>>('/api/versions/', { params }).pipe(
      map((wire) => ({
        ...wire,
        results: wire.results.map((version) => ({
          id: version.id,
          number: version.number,
          name: version.name,
          isActive: version.is_active,
        })),
      })),
    );
  }

  datasets(page: number): Observable<Page<LibraryDataset>> {
    const params = new HttpParams({ fromObject: { page, page_size: DATASETS_PAGE_SIZE } });
    return this.http.get<Page<DatasetWire>>('/api/datasets/', { params }).pipe(
      map((wire) => ({
        ...wire,
        results: wire.results
          .filter((dataset) => dataset.status === 'ready')
          .map((dataset) => ({
            id: dataset.id,
            name: dataset.name,
            rows: dataset.rows,
            hasThinking: dataset.has_thinking,
          })),
      })),
    );
  }

  projectNames(ids: readonly string[]): Observable<SourceNames> {
    return forkJoin(
      ids.map((id) =>
        this.http.get<ProjectNameWire>(`/api/projects/${id}/`).pipe(
          map((project): readonly [string, string] | null => [id, project.name]),
          catchError(() => of(null)),
        ),
      ),
    ).pipe(map((entries) => Object.fromEntries(entries.filter((entry) => entry !== null))));
  }

  versionSize(id: string): Observable<VersionSize> {
    return this.http
      .get<VersionWire>(`/api/versions/${id}/`)
      .pipe(map((version) => ({ sizeBytes: version.size_bytes, fullSizeBytes: version.full_size_bytes })));
  }
}
