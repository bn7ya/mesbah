import { Injectable } from '@angular/core';
import { Subject, type Observable } from 'rxjs';

import type { ActiveVersionChange } from './version.types';

@Injectable({ providedIn: 'root' })
export class ActiveVersionChanges {
  private readonly announced = new Subject<ActiveVersionChange>();

  readonly changes: Observable<ActiveVersionChange> = this.announced.asObservable();

  announce(change: ActiveVersionChange): void {
    this.announced.next(change);
  }
}
