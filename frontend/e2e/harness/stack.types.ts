export interface Stack {
  readonly base_url: string;
  readonly engine_url: string;
  readonly data_dir: string;
  readonly setup_code: string;
  readonly version: string;
  readonly mesbah_pid: number;
  readonly engine_pid: number;
  readonly logs: string;
}
