import { HttpClient, HttpParams, type HttpEvent } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';

import type { Page, PageQuery } from '@core/http/api.types';
import type {
  Conversation,
  Dataset,
  DatasetChanges,
  HubDataset,
  InspectQuery,
  Inspection,
  NewImport,
} from './datasets.types';

@Injectable({ providedIn: 'root' })
export class DatasetsApi {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/datasets';

  library(query: PageQuery): Observable<Page<Dataset>> {
    const params = new HttpParams({ fromObject: { ...query } });
    return this.http.get<Page<Dataset>>(`${this.base}/`, { params });
  }

  find(id: string): Observable<Dataset> {
    return this.http.get<Dataset>(`${this.base}/${id}/`);
  }

  import(request: NewImport): Observable<Dataset> {
    return this.http.post<Dataset>(`${this.base}/`, request);
  }

  upload(file: File, name: string): Observable<HttpEvent<Dataset>> {
    const body = new FormData();
    body.append('file', file, file.name);
    body.append('name', name);
    return this.http.post<Dataset>(`${this.base}/upload/`, body, { observe: 'events', reportProgress: true });
  }

  update(id: string, changes: DatasetChanges): Observable<Dataset> {
    return this.http.patch<Dataset>(`${this.base}/${id}/`, changes);
  }

  remove(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}/`);
  }

  cancel(id: string): Observable<Dataset> {
    return this.http.post<Dataset>(`${this.base}/${id}/cancel/`, null);
  }

  retry(id: string): Observable<Dataset> {
    return this.http.post<Dataset>(`${this.base}/${id}/retry/`, null);
  }

  rows(id: string, query: PageQuery): Observable<Page<Conversation>> {
    const params = new HttpParams({ fromObject: { ...query } });
    return this.http.get<Page<Conversation>>(`${this.base}/${id}/rows/`, { params });
  }

  hub(search: string): Observable<Page<HubDataset>> {
    const words = search.trim();
    const params = words === '' ? new HttpParams() : new HttpParams({ fromObject: { search: words } });
    return this.http.get<Page<HubDataset>>(`${this.base}/hub/`, { params });
  }

  inspect(query: InspectQuery): Observable<Inspection> {
    const fields: Record<string, string> = { repo: query.repo };
    if (query.config) {
      fields['config'] = query.config;
    }
    if (query.split) {
      fields['split'] = query.split;
    }
    if (query.columns) {
      fields['prompt'] = query.columns.prompt;
      fields['reply'] = query.columns.reply;
      fields['thinking'] = query.columns.thinking;
    }
    return this.http.get<Inspection>(`${this.base}/hub/inspect/`, { params: new HttpParams({ fromObject: fields }) });
  }
}
