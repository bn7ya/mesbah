import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  effect,
  inject,
  input,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import type { Chart, ChartConfiguration } from 'chart.js';

import { LocaleStore } from '@core/i18n/locale.store';
import type { ChartData, ChartPalette, ChartSnapshot } from '../../data/training.types';

const NUMBER_LOCALES: Readonly<Record<string, string>> = {
  en: 'en-u-nu-latn',
  ar: 'ar-u-nu-latn',
};

const FILL_SHARE = '14%';
const LINE_WIDTH = 2;
const DOT_LIMIT = 60;
const TICK_LIMIT = 8;
const FONT_SIZE = 12;

@Component({
  selector: 'app-run-chart',
  templateUrl: './run-chart.html',
  styleUrl: './run-chart.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RunChart {
  private readonly locale = inject(LocaleStore);
  private readonly scheme = signal(0);

  readonly chart = input.required<ChartData>();

  private readonly canvas = viewChild.required<ElementRef<HTMLCanvasElement>>('canvas');
  private readonly primary = viewChild.required<ElementRef<HTMLElement>>('primary');
  private readonly tertiary = viewChild.required<ElementRef<HTMLElement>>('tertiary');
  private readonly grid = viewChild.required<ElementRef<HTMLElement>>('grid');
  private readonly text = viewChild.required<ElementRef<HTMLElement>>('text');

  private instance: Chart | null = null;
  private shape = '';
  private waiting: ChartSnapshot | null = null;
  private drawing = false;
  private gone = false;

  constructor() {
    const media = typeof matchMedia === 'function' ? matchMedia('(prefers-color-scheme: dark)') : null;
    const repaint = (): void => this.scheme.update((count) => count + 1);
    media?.addEventListener('change', repaint);

    inject(DestroyRef).onDestroy(() => {
      this.gone = true;
      media?.removeEventListener('change', repaint);
      this.instance?.destroy();
      this.instance = null;
    });

    effect(() => {
      const snapshot: ChartSnapshot = {
        data: this.chart(),
        rtl: this.locale.isRtl(),
        locale: this.locale.locale(),
        scheme: this.scheme(),
      };
      untracked(() => {
        this.waiting = snapshot;
        void this.flush();
      });
    });
  }

  private async flush(): Promise<void> {
    if (this.drawing) {
      return;
    }
    this.drawing = true;
    try {
      const { default: ChartJs } = await import('chart.js/auto');
      while (this.waiting !== null && !this.gone) {
        const snapshot = this.waiting;
        this.waiting = null;
        this.draw(ChartJs, snapshot);
      }
    } finally {
      this.drawing = false;
    }
  }

  private draw(ChartJs: typeof Chart, snapshot: ChartSnapshot): void {
    const { data, rtl, locale, scheme } = snapshot;
    const shape = JSON.stringify([
      rtl,
      locale,
      scheme,
      data.stepTitle,
      data.series.map((series) => [series.id, series.label, series.axis, series.axisTitle]),
    ]);

    if (this.instance !== null && shape === this.shape) {
      const instance = this.instance;
      instance.data.labels = [...data.steps];
      data.series.forEach((series, index) => {
        instance.data.datasets[index].data = [...series.values];
      });
      instance.update('none');
      return;
    }

    this.instance?.destroy();
    const element = this.canvas().nativeElement;
    const palette = this.palette();
    ChartJs.defaults.font.family = getComputedStyle(element).fontFamily;
    ChartJs.defaults.font.size = FONT_SIZE;
    this.instance = new ChartJs(element, this.configure(snapshot, palette));
    this.shape = shape;
  }

  private palette(): ChartPalette {
    const read = (reference: ElementRef<HTMLElement>): string => getComputedStyle(reference.nativeElement).color;
    return {
      primary: read(this.primary()),
      tertiary: read(this.tertiary()),
      grid: read(this.grid()),
      text: read(this.text()),
    };
  }

  private configure(snapshot: ChartSnapshot, palette: ChartPalette): ChartConfiguration<'line'> {
    const { data, rtl, locale } = snapshot;
    const dots = data.steps.length <= DOT_LIMIT ? 3 : 0;
    const single = data.series.length === 1;
    const direction = rtl ? 'rtl' : 'ltr';
    const title = (text: string) => ({ display: true, text, color: palette.text });

    return {
      type: 'line',
      data: {
        labels: [...data.steps],
        datasets: data.series.map((series) => {
          const color = series.color === 'primary' ? palette.primary : palette.tertiary;
          return {
            label: series.label,
            data: [...series.values],
            borderColor: color,
            backgroundColor: single ? `color-mix(in srgb, ${color} ${FILL_SHARE}, transparent)` : color,
            fill: single,
            borderWidth: LINE_WIDTH,
            pointRadius: dots,
            pointHoverRadius: dots + 2,
            tension: 0.2,
            spanGaps: true,
            yAxisID: series.axis === 'left' ? 'y' : 'y1',
          };
        }),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        locale: NUMBER_LOCALES[locale],
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            display: !single,
            rtl,
            textDirection: direction,
            labels: { color: palette.text },
          },
          tooltip: {
            rtl,
            textDirection: direction,
            callbacks: {
              title: (items) => `${data.stepTitle}: ${items[0]?.label ?? ''}`,
            },
          },
        },
        scales: {
          x: {
            reverse: rtl,
            title: title(data.stepTitle),
            grid: { color: palette.grid },
            ticks: { color: palette.text, maxTicksLimit: TICK_LIMIT },
          },
          y: {
            position: rtl ? 'right' : 'left',
            title: title(data.series.find((series) => series.axis === 'left')?.axisTitle ?? ''),
            grid: { color: palette.grid },
            ticks: { color: palette.text },
          },
          ...(data.series.some((series) => series.axis === 'right')
            ? {
                y1: {
                  position: rtl ? ('left' as const) : ('right' as const),
                  title: title(data.series.find((series) => series.axis === 'right')?.axisTitle ?? ''),
                  grid: { drawOnChartArea: false },
                  ticks: { color: palette.text },
                },
              }
            : {}),
        },
      },
    };
  }
}
