import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';

import type { GpuSelection, HuggingFaceToken, SystemOverview } from './system.types';

@Injectable({ providedIn: 'root' })
export class SystemApi {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/system';

  overview(): Observable<SystemOverview> {
    return this.http.get<SystemOverview>(`${this.base}/`);
  }

  selectGpus(selection: GpuSelection): Observable<SystemOverview> {
    return this.http.put<SystemOverview>(`${this.base}/gpus/`, selection);
  }

  saveHuggingFaceToken(token: HuggingFaceToken): Observable<SystemOverview> {
    return this.http.put<SystemOverview>(`${this.base}/huggingface-token/`, token);
  }

  removeHuggingFaceToken(): Observable<SystemOverview> {
    return this.http.delete<SystemOverview>(`${this.base}/huggingface-token/`);
  }
}
