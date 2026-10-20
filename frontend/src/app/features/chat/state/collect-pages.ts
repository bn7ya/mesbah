import { EMPTY, expand, reduce, type Observable } from 'rxjs';

import type { Page } from '@core/http/api.types';

export function collectPages<T>(fetch: (page: number) => Observable<Page<T>>): Observable<readonly T[]> {
  return fetch(1).pipe(
    expand((page, index) => (page.next === null ? EMPTY : fetch(index + 2))),
    reduce((all: readonly T[], page: Page<T>) => [...all, ...page.results], [] as readonly T[]),
  );
}
