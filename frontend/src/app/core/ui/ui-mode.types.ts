export type UiMode = 'simple' | 'expert';

export interface UiModeOption {
  readonly value: UiMode;
  readonly label: string;
}

export const UI_MODES: readonly UiMode[] = ['simple', 'expert'];
