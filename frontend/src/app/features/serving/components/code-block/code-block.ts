import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import { CopyButton } from '../copy-button/copy-button';

@Component({
  selector: 'app-code-block',
  imports: [CopyButton],
  templateUrl: './code-block.html',
  styleUrl: './code-block.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CodeBlock {
  readonly label = input.required<string>();
  readonly code = input.required<string>();
}
