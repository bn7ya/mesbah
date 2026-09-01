import { Component, Input } from '@angular/core';
import { TooltipModule } from 'primeng/tooltip';
import { ModelFit } from './types';

const LABEL: Record<ModelFit['tier'], string> = {
  comfortable: 'يعمل بسلاسة مع عتادك',
  tight: 'قد يكون بطيئًا على عتادك',
  too_large: 'أكبر من عتادك الحالي',
  unknown: '',
};
const ICON: Record<ModelFit['tier'], string> = {
  comfortable: '🟢', tight: '🟡', too_large: '🔴', unknown: '',
};

/** Plain-language "does this fit my GPU" badge for a `HubModel.fit` verdict.
 * Shared by the project-creation model picker and the standalone models page —
 * same data (`GET /models/featured|search`), same visual. Renders nothing for
 * an `unknown` tier (unparsed model size). */
@Component({
  selector: 'app-model-fit-badge',
  imports: [TooltipModule],
  template: `
    @if (fit && fit.tier !== 'unknown') {
      <span class="inline-flex items-center gap-1 text-xs whitespace-nowrap"
            [pTooltip]="tooltipText()" tooltipPosition="top">
        <span>{{ icon() }}</span><span>{{ label() }}</span>
      </span>
    }
  `,
})
export class ModelFitBadge {
  @Input() fit?: ModelFit | null;

  label(): string { return this.fit ? LABEL[this.fit.tier] : ''; }
  icon(): string { return this.fit ? ICON[this.fit.tier] : ''; }
  tooltipText(): string {
    const gb = this.fit?.required_gb;
    return gb ? `يحتاج تقريبًا ${gb} GB VRAM (تقدير تقريبي)` : '';
  }
}
