import { Injectable, effect, inject } from '@angular/core';
import { MatPaginatorIntl } from '@angular/material/paginator';

import { LocaleStore } from './locale.store';

@Injectable()
export class LocalePaginatorIntl extends MatPaginatorIntl {
  private readonly locale = inject(LocaleStore);

  constructor() {
    super();
    effect(() => {
      this.locale.locale();
      this.itemsPerPageLabel = this.locale.translate('paginator.perPage');
      this.nextPageLabel = this.locale.translate('paginator.next');
      this.previousPageLabel = this.locale.translate('paginator.previous');
      this.firstPageLabel = this.locale.translate('paginator.first');
      this.lastPageLabel = this.locale.translate('paginator.last');
      this.changes.next();
    });
  }

  override getRangeLabel = (page: number, pageSize: number, length: number): string => {
    if (length === 0) {
      return this.locale.translate('paginator.empty');
    }
    const from = page * pageSize + 1;
    const to = Math.min(length, (page + 1) * pageSize);
    return this.locale.translate('paginator.range', { from, to, total: length });
  };
}
