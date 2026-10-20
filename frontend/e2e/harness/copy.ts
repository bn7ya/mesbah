import { randomInt } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import type { Bundle, Strings, UiLocale, Values } from './copy.types';
import { FRONTEND } from './stack';

const APP = join(FRONTEND, 'src', 'app');
const ISOLATES = '[\\u2066-\\u2069]*';
const PLACEHOLDER = /\{(\w+)\}/g;
const ANY_VALUE = '[\\s\\S]+?';
const loaded = new Map<string, ReadonlyMap<string, string>>();

function folder(bundle: Bundle): string {
  return bundle === 'core' ? join(APP, 'core', 'i18n') : join(APP, 'features', bundle, 'i18n');
}

function isStrings(value: unknown): value is Strings {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function flatten(node: Strings, prefix: string, into: Map<string, string>): void {
  for (const [key, value] of Object.entries(node)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === 'string') {
      into.set(path, value);
    } else {
      flatten(value, path, into);
    }
  }
}

function dictionary(bundle: Bundle, locale: UiLocale): ReadonlyMap<string, string> {
  const name = `${bundle}/${locale}`;
  const kept = loaded.get(name);
  if (kept) {
    return kept;
  }
  const parsed: unknown = JSON.parse(readFileSync(join(folder(bundle), `${locale}.json`), 'utf8'));
  if (!isStrings(parsed)) {
    throw new Error(`${name}.json is not a bundle`);
  }
  const flat = new Map<string, string>();
  flatten(parsed, '', flat);
  loaded.set(name, flat);
  return flat;
}

function escaped(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function template(bundle: Bundle, locale: UiLocale, key: string): string {
  const found = dictionary(bundle, locale).get(key);
  if (found === undefined) {
    throw new Error(`${bundle}/${locale}.json has no ${key}`);
  }
  return found;
}

export function text(bundle: Bundle, locale: UiLocale, key: string, values: Values = {}): string {
  return template(bundle, locale, key).replace(PLACEHOLDER, (match, name: string) =>
    name in values ? String(values[name]) : match,
  );
}

function source(bundle: Bundle, locale: UiLocale, key: string, values: Values): string {
  return template(bundle, locale, key)
    .split(PLACEHOLDER)
    .map((piece, index) =>
      index % 2 === 0 ? escaped(piece) : `${ISOLATES}${escaped(String(values[piece] ?? `{${piece}}`))}${ISOLATES}`,
    )
    .join('');
}

// The page isolates a value written in the other script with U+2068…U+2069, so a name read
// back carries those marks around each value; a required field's label ends in an asterisk.
export function label(bundle: Bundle, locale: UiLocale, key: string, values: Values = {}): RegExp {
  return new RegExp(`^\\s*${source(bundle, locale, key, values)}\\s*\\*?\\s*$`);
}

export function contains(bundle: Bundle, locale: UiLocale, key: string, values: Values = {}): RegExp {
  return new RegExp(source(bundle, locale, key, values));
}

export function anyValues(bundle: Bundle, locale: UiLocale, ...keys: readonly string[]): RegExp {
  const sources = keys.map((key) =>
    template(bundle, locale, key)
      .split(PLACEHOLDER)
      .map((piece, index) => (index % 2 === 0 ? escaped(piece) : ANY_VALUE))
      .join(''),
  );
  return new RegExp(sources.map((one) => `(?:${one})`).join('|'));
}

export function literal(value: string): RegExp {
  return new RegExp(escaped(value));
}

export function startsWith(value: string): RegExp {
  return new RegExp(`^[\\s\\u2066-\\u2069]*${escaped(value)}`);
}

export function stamp(): string {
  return `${Date.now() % 1_000_000_000}${String(randomInt(1000)).padStart(3, '0')}`;
}
