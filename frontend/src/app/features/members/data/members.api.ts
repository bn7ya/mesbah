import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';

import type { Page, PageQuery } from '@core/http/api.types';
import type { Member, MemberChange, NewMember } from './members.types';

@Injectable({ providedIn: 'root' })
export class MembersApi {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/members';

  list(query: PageQuery): Observable<Page<Member>> {
    const params = new HttpParams({ fromObject: { ...query } });
    return this.http.get<Page<Member>>(`${this.base}/`, { params });
  }

  add(member: NewMember): Observable<Member> {
    return this.http.post<Member>(`${this.base}/`, member);
  }

  change(id: number, change: MemberChange): Observable<Member> {
    return this.http.patch<Member>(`${this.base}/${id}/`, change);
  }
}
