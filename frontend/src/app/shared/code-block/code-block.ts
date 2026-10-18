import { ChangeDetectionStrategy, Component, input } from '@angular/core';

@Component({
  selector: 'app-code-block',
  templateUrl: './code-block.html',
  styleUrl: './code-block.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CodeBlock {
  readonly code = input.required<string>();
  readonly label = input<string | null>(null);
}
