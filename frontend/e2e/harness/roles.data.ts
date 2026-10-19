import type { Expectation, Expectations } from './roles.types';

const REFUSED: Expectation = { status: 403, code: 'permission_denied' };
const INVALID: Expectation = { status: 400, code: 'invalid' };

export const VIEWER_WRITES: Expectations = {
  auth_login_create: INVALID,
  auth_logout_create: { status: 204, code: null, ownSession: true },
  auth_setup_create: {
    status: 409,
    code: 'setup_done',
    body: { code: '000000', username: 'intruder', password: 'not-the-owner-9' },
  },

  architect_estimate: INVALID,
  architect_drafts_create: REFUSED,
  architect_drafts_partial_update: REFUSED,
  architect_drafts_destroy: REFUSED,
  architect_train: REFUSED,

  chat_create: REFUSED,
  chat_partial_update: REFUSED,
  chat_destroy: REFUSED,
  chat_reply: REFUSED,
  chat_messages_partial_update: REFUSED,
  chat_messages_restore_create: REFUSED,
  chat_messages_approve_create: REFUSED,

  datasets_import: REFUSED,
  datasets_upload: REFUSED,
  datasets_update: REFUSED,
  datasets_remove: REFUSED,
  datasets_cancel: REFUSED,
  datasets_retry: REFUSED,

  members_create: REFUSED,
  members_partial_update: REFUSED,

  models_create: REFUSED,
  models_destroy: REFUSED,
  models_cancel_create: REFUSED,
  models_retry_create: REFUSED,

  projects_create: REFUSED,
  projects_partial_update: REFUSED,
  projects_destroy: REFUSED,

  serving_engines_create: REFUSED,
  serving_engines_partial_update: REFUSED,
  serving_engines_destroy: REFUSED,
  serving_engines_unload_create: REFUSED,
  serving_keys_create: REFUSED,
  serving_keys_destroy: REFUSED,

  system_gpus_update: REFUSED,
  system_huggingface_token_update: REFUSED,
  system_huggingface_token_destroy: REFUSED,

  training_create: REFUSED,
  training_destroy: REFUSED,
  training_cancel_create: REFUSED,

  versions_partial_update: REFUSED,
  versions_destroy: REFUSED,
  versions_activate_create: REFUSED,
  versions_exports_create: REFUSED,
  versions_exports_destroy: REFUSED,
};
