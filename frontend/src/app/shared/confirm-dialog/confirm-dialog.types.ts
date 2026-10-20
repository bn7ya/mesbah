export interface ConfirmDialogData {
  readonly titleKey: string;
  readonly bodyKey: string;
  readonly confirmKey: string;
  readonly values?: Readonly<Record<string, string | number>>;
  readonly destructive?: boolean;
}
