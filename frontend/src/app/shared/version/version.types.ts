export interface VersionLabel {
  readonly id: string;
  readonly number: number;
  readonly name: string;
}

export interface ActiveVersionChange {
  readonly projectId: string;
  readonly version: VersionLabel;
}

export const ROOT_NUMBER = 0;

export const SEEDED_ROOT_NAME = 'base';
