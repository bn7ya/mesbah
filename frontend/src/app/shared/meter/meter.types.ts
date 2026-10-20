export type MeterTone = 'primary' | 'tertiary' | 'secondary' | 'error';

export interface MeterSegment {
  readonly label: string;
  readonly bytes: number;
  readonly tone: MeterTone;
}

export interface MeterSlice extends MeterSegment {
  readonly share: number;
}
