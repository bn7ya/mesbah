import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';

import { TranslatePipe } from '@core/i18n/translate.pipe';
import { VersionNamePipe } from '@shared/version/version-name.pipe';
import type { LoadedVersion } from '../../data/serving.types';

@Component({
  selector: 'app-loaded-versions',
  imports: [RouterLink, TranslatePipe, VersionNamePipe],
  templateUrl: './loaded-versions.html',
  styleUrl: './loaded-versions.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LoadedVersions {
  readonly versions = input.required<readonly LoadedVersion[]>();
}
