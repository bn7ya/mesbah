import { Directionality } from '@angular/cdk/bidi';
import { Injectable, computed, effect, inject, signal, untracked } from '@angular/core';

import ar from './ar.json';
import en from './en.json';
import { DIRECTION, LOCALES, type Direction, type Locale, type TranslationBundle, type TranslationSet } from './locale.types';

const STORAGE_KEY = 'locale';
const OPPOSITE_SCRIPT: Readonly<Record<Direction, RegExp>> = { rtl: /[A-Za-z]/, ltr: /[\u0590-\u08ff]/ };
const ISOLATES: readonly string[] = ['\u2066', '\u2067', '\u2068'];

@Injectable({ providedIn: 'root' })
export class LocaleStore {
  private readonly directionality = inject(Directionality);

  private readonly bundles = signal<readonly TranslationSet[]>([{ en, ar }]);

  readonly locale = signal<Locale>(readInitialLocale());

  readonly direction = computed<Direction>(() => DIRECTION[this.locale()]);

  readonly isRtl = computed(() => this.direction() === 'rtl');

  private readonly dictionary = computed<ReadonlyMap<string, string>>(() => {
    const active = this.locale();
    const flat = new Map<string, string>();
    for (const set of this.bundles()) {
      flatten(set[active], '', flat);
    }
    return flat;
  });

  constructor() {
    effect(() => {
      const locale = this.locale();
      const direction = DIRECTION[locale];
      document.documentElement.lang = locale;
      document.documentElement.dir = direction;
      localStorage.setItem(STORAGE_KEY, locale);

      if (untracked(this.directionality.valueSignal) !== direction) {
        this.directionality.valueSignal.set(direction);
        this.directionality.change.emit(direction);
      }
    });
  }

  translate(key: string, values?: Readonly<Record<string, string | number>>): string {
    const template = this.dictionary().get(key) ?? key;
    if (!values) {
      return template;
    }
    const direction = this.direction();
    return template.replace(/\{(\w+)\}/g, (match, name: string) =>
      name in values ? isolated(String(values[name]), direction) : match,
    );
  }

  setLocale(locale: Locale): void {
    this.locale.set(locale);
  }

  register(set: TranslationSet): void {
    this.bundles.update((current) => (current.includes(set) ? current : [...current, set]));
  }
}

function flatten(bundle: TranslationBundle, prefix: string, into: Map<string, string>): void {
  for (const [key, value] of Object.entries(bundle)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === 'string') {
      into.set(path, value);
    } else {
      flatten(value, path, into);
    }
  }
}

function readInitialLocale(): Locale {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (isLocale(stored)) {
    return stored;
  }
  return 'ar';
}

function isLocale(value: string | null): value is Locale {
  return value !== null && (LOCALES as readonly string[]).includes(value);
}

// A value in the other script keeps its own direction inside the sentence, so a name's
// punctuation stays beside it; values already isolated are left as they are.
function isolated(text: string, direction: Direction): string {
  if (!OPPOSITE_SCRIPT[direction].test(text) || ISOLATES.some((mark) => text.startsWith(mark))) {
    return text;
  }
  return `\u2068${text}\u2069`;
}
