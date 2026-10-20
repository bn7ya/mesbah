import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { MAX_INDENT_DEPTH, type VersionNode } from '../../data/versions.types';
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
  readonly depth = input(0);

  readonly flat = computed(() => this.depth() >= MAX_INDENT_DEPTH);
}
