import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';

import { LocaleStore } from '@core/i18n/locale.store';
import { versionName } from '@shared/version/version-name.pipe';
import type { VersionRef as Ref } from '../../data/training.types';

@Component({
  selector: 'app-version-ref',
  templateUrl: './version-ref.html',
  styleUrl: './version-ref.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VersionRef {
  private readonly locale = inject(LocaleStore);

  readonly version = input.required<Pick<Ref, 'number' | 'name'>>();

  readonly name = computed(() => {
    const version = this.version();
    const name = versionName(version, this.locale);
    return name === '' || name === `v${version.number}` ? null : name;
  });
}
