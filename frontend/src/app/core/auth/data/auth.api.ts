import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';

import type { Credentials, Identity } from './auth.types';

@Injectable({ providedIn: 'root' })
export class AuthApi {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/auth';

  primeCsrf(): Observable<void> {
    return this.http.get<void>(`${this.base}/csrf/`);
  }

  signIn(credentials: Credentials): Observable<Identity> {
    return this.http.post<Identity>(`${this.base}/login/`, credentials);
  }

  signOut(): Observable<void> {
    return this.http.post<void>(`${this.base}/logout/`, {});
  }

  me(): Observable<Identity> {
    return this.http.get<Identity>(`${this.base}/me/`);
  }
}
