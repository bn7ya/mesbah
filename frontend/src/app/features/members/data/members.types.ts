import type { Role } from '@core/auth/roles.types';

export interface Member {
  readonly id: number;
  readonly username: string;
  readonly first_name: string;
  readonly last_name: string;
  readonly email: string;
  readonly role: Role | null;
  readonly owner: boolean;
  readonly is_active: boolean;
  readonly is_self: boolean;
  readonly last_login: string | null;
  readonly date_joined: string;
}

export interface NewMember {
  readonly username: string;
  readonly password: string;
  readonly role: Role;
  readonly first_name: string;
  readonly last_name: string;
  readonly email: string;
}

export interface MemberChange {
  readonly role?: Role;
  readonly is_active?: boolean;
}
