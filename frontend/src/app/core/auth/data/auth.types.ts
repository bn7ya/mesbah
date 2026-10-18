export interface Identity {
  readonly id: number;
  readonly username: string;
  readonly email: string;
  readonly first_name: string;
  readonly last_name: string;
  readonly is_staff: boolean;
  readonly is_superuser: boolean;
  readonly groups: readonly string[];
  readonly permissions: readonly string[];
}

export interface Credentials {
  readonly username: string;
  readonly password: string;
}
