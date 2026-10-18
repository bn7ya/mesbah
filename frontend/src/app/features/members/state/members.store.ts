import { Injectable, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { EMPTY_PAGE, type ApiError, type Page } from '@core/http/api.types';
import { MembersApi } from '../data/members.api';
import type { Member, MemberChange, NewMember } from '../data/members.types';

const PAGE_SIZE = 25;

@Injectable()
export class MembersStore {
  private readonly api = inject(MembersApi);

  readonly page = signal<Page<Member>>(EMPTY_PAGE);
  readonly pageIndex = signal(0);
  readonly pageSize = signal(PAGE_SIZE);
  readonly loading = signal(false);
  readonly busy = signal(false);
  readonly error = signal<ApiError | null>(null);

  async load(pageIndex = this.pageIndex(), pageSize = this.pageSize()): Promise<void> {
    this.loading.set(true);
    this.error.set(null);
    try {
      this.page.set(await firstValueFrom(this.api.list({ page: pageIndex + 1, page_size: pageSize })));
      this.pageIndex.set(pageIndex);
      this.pageSize.set(pageSize);
    } catch (error) {
      this.error.set(error as ApiError);
    } finally {
      this.loading.set(false);
    }
  }

  async add(member: NewMember): Promise<ApiError | null> {
    this.busy.set(true);
    try {
      await firstValueFrom(this.api.add(member));
      await this.load();
      return null;
    } catch (error) {
      return error as ApiError;
    } finally {
      this.busy.set(false);
    }
  }

  async change(member: Member, change: MemberChange): Promise<boolean> {
    this.busy.set(true);
    this.error.set(null);
    try {
      const updated = await firstValueFrom(this.api.change(member.id, change));
      this.page.update((page) => ({
        ...page,
        results: page.results.map((row) => (row.id === updated.id ? updated : row)),
      }));
      return true;
    } catch (error) {
      this.error.set(error as ApiError);
      return false;
    } finally {
      this.busy.set(false);
    }
  }
}
