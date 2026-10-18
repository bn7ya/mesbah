import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';

import type { Page } from '@core/http/api.types';
import { PAGE_SIZE, type Version, type VersionChange } from './versions.types';

@Injectable({ providedIn: 'root' })
export class VersionsApi {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/versions';

  tree(project: string, page: number): Observable<Page<Version>> {
    const params = new HttpParams({ fromObject: { project, page, page_size: PAGE_SIZE } });
    return this.http.get<Page<Version>>(`${this.base}/`, { params });
  }

  activate(id: string): Observable<Version> {
    return this.http.post<Version>(`${this.base}/${id}/activate/`, null);
  }

  change(id: string, change: VersionChange): Observable<Version> {
    return this.http.patch<Version>(`${this.base}/${id}/`, change);
  }

  remove(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}/`);
  }
}
