export type UiLocale = 'en' | 'ar';

export type Bundle =
  | 'core'
  | 'architect'
  | 'chat'
  | 'datasets'
  | 'members'
  | 'models'
  | 'projects'
  | 'serving'
  | 'system'
  | 'training'
  | 'versions';

export interface Strings {
  readonly [key: string]: string | Strings;
}

export type Values = Readonly<Record<string, string | number>>;

export type Copy = (bundle: Bundle, key: string, values?: Values) => RegExp;
