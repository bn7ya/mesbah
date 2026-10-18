import {
  SETTING_LABELS,
  SIMPLE_SETTING_KEYS,
  type RunHyperparams,
  type RunSettingKey,
} from '../data/training.types';

export function settingValue(used: RunHyperparams, key: RunSettingKey): number | boolean | string | null | undefined {
  return key === 'optim' ? used.pretrain?.optim : used[key];
}

export function shownSettings(used: RunHyperparams, expert: boolean): readonly RunSettingKey[] {
  return (Object.keys(SETTING_LABELS) as RunSettingKey[]).filter(
    (key) => settingValue(used, key) !== undefined && (expert || SIMPLE_SETTING_KEYS.includes(key)),
  );
}
