export interface VersionRow {
  readonly id: string;
  readonly number: number;
  readonly name: string;
  readonly kind: string;
  readonly parentId: string | null;
  readonly isActive: boolean;
  readonly sizeBytes: number;
  readonly fullSizeBytes: number;
}
