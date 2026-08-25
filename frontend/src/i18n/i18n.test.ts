import { describe, it, expect } from 'vitest';
import da from './locales/da.json';
import en from './locales/en.json';

function getNestedKeys(obj: Record<string, any>, prefix = ''): string[] {
  let keys: string[] = [];
  for (const [key, value] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key;
    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      keys = keys.concat(getNestedKeys(value, fullKey));
    } else {
      keys.push(fullKey);
    }
  }
  return keys;
}

describe('i18n Locale Dictionaries', () => {
  it('contains consistent translation keys between da and en', () => {
    const daKeys = getNestedKeys(da).sort();
    const enKeys = getNestedKeys(en).sort();

    const missingInEn = daKeys.filter((k) => !enKeys.includes(k));
    const missingInDa = enKeys.filter((k) => !daKeys.includes(k));

    expect(missingInEn, `Keys present in da.json but missing in en.json: ${missingInEn.join(', ')}`).toEqual([]);
    expect(missingInDa, `Keys present in en.json but missing in da.json: ${missingInDa.join(', ')}`).toEqual([]);
  });

  it('includes required transaction action and summary keys', () => {
    expect(da.transactions).toHaveProperty('itemsSelected');
    expect(da.transactions).toHaveProperty('rememberRuleTitle');
    expect(da.transactions).toHaveProperty('rememberRuleBody');
    expect(da.transactions).toHaveProperty('noThanks');
    expect(da.budgets).toHaveProperty('kr_per_month');

    expect(en.transactions).toHaveProperty('itemsSelected');
    expect(en.transactions).toHaveProperty('rememberRuleTitle');
    expect(en.transactions).toHaveProperty('rememberRuleBody');
    expect(en.transactions).toHaveProperty('noThanks');
    expect(en.budgets).toHaveProperty('kr_per_month');
  });
});
