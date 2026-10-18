import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import type { VersionNode } from '../../data/versions.types';
import { VersionRow } from '../version-row/version-row';

@Component({
  selector: 'app-version-branch',
  imports: [VersionRow],
  templateUrl: './version-branch.html',
  styleUrl: './version-branch.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VersionBranch {
  readonly node = input.required<VersionNode>();
}
