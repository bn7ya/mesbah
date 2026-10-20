import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';

import type { Page, PageQuery } from '@core/http/api.types';
import type { HubQuery, HubResult, Inspection, LibraryModel, NewModel } from './models.types';

@Injectable({ providedIn: 'root' })
export class ModelsApi {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/models';

  library(query: PageQuery): Observable<Page<LibraryModel>> {
    const params = new HttpParams({ fromObject: { ...query } });
    return this.http.get<Page<LibraryModel>>(`${this.base}/`, { params });
  }

  add(model: NewModel): Observable<LibraryModel> {
    return this.http.post<LibraryModel>(`${this.base}/`, model);
  }

  cancel(id: string): Observable<LibraryModel> {
    return this.http.post<LibraryModel>(`${this.base}/${id}/cancel/`, null);
  }

  retry(id: string): Observable<LibraryModel> {
    return this.http.post<LibraryModel>(`${this.base}/${id}/retry/`, null);
  }

  remove(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}/`);
  }

  hub(query: HubQuery): Observable<Page<HubResult>> {
    const search = query.search.trim();
    const params = search === '' ? new HttpParams() : new HttpParams({ fromObject: { search, task: query.task } });
    return this.http.get<Page<HubResult>>(`${this.base}/hub/`, { params });
  }

  inspect(repo: string): Observable<Inspection> {
    const params = new HttpParams({ fromObject: { repo } });
    return this.http.get<Inspection>(`${this.base}/hub/inspect/`, { params });
  }
}
