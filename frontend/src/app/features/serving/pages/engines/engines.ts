import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButton } from '@angular/material/button';
import { MatProgressBar } from '@angular/material/progress-bar';

import { TranslatePipe } from '@core/i18n/translate.pipe';
import { Note } from '@shared/note/note';
import { Term } from '@shared/term/term';
import { ApiKeys } from '../../components/api-keys/api-keys';
import { BuiltinEngine } from '../../components/builtin-engine/builtin-engine';
import { ConnectGuide } from '../../components/connect-guide/connect-guide';
import { OtherEngines } from '../../components/other-engines/other-engines';
import { ServingStore } from '../../state/serving.store';

@Component({
  selector: 'app-engines-page',
  imports: [
    ApiKeys,
    BuiltinEngine,
    ConnectGuide,
    MatButton,
    MatProgressBar,
    Note,
    OtherEngines,
    Term,
    TranslatePipe,
  ],
  templateUrl: './engines.html',
  styleUrl: './engines.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EnginesPage {
  private readonly store = inject(ServingStore);

  readonly builtin = this.store.builtin;
  readonly loading = this.store.loading;
  readonly loaded = this.store.loaded;
  readonly error = this.store.error;

  constructor() {
    void this.store.visit();
    this.store.watch().pipe(takeUntilDestroyed()).subscribe();
  }

  tryAgain(): void {
    void this.store.load();
  }
}
