import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { MatExpansionPanel, MatExpansionPanelHeader, MatExpansionPanelTitle } from '@angular/material/expansion';
import { MatIcon } from '@angular/material/icon';

import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { Conversation } from '../../data/datasets.types';

@Component({
  selector: 'app-dataset-conversation',
  imports: [MatExpansionPanel, MatExpansionPanelHeader, MatExpansionPanelTitle, MatIcon, TranslatePipe],
  templateUrl: './conversation.html',
  styleUrl: './conversation.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DatasetConversation {
  readonly conversation = input.required<Conversation>();
  readonly number = input.required<number>();
}
