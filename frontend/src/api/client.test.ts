import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  setApiToken,
  setHouseholdId,
  getHouseholdId,
  getHeaders,
  fetchTransactions,
  fetchBudgets,
  generateBudgets,
  applyBudgetSuggestions,
} from './client';

describe('API Client & HTTP Configuration', () => {
  beforeEach(() => {
    setApiToken('');
    setHouseholdId('');
    vi.restoreAllMocks();
  });

  it('manages authorization token and household ID headers', () => {
    expect(getHeaders()).toEqual({
      'Content-Type': 'application/json',
    });

    setApiToken('test-jwt-token');
    expect(getHeaders()).toEqual({
      'Content-Type': 'application/json',
      Authorization: 'Bearer test-jwt-token',
    });

    setHouseholdId('hh-12345');
    expect(getHouseholdId()).toBe('hh-12345');
    expect(getHeaders()).toEqual({
      'Content-Type': 'application/json',
      Authorization: 'Bearer test-jwt-token',
      'X-Household-Id': 'hh-12345',
    });
  });

  it('constructs correct query parameters for fetchTransactions', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ postings: [], total: 0 }),
    });
    global.fetch = mockFetch;

    setHouseholdId('hh-abc');
    await fetchTransactions(25, 50, 'Forbrug', 'dagligvarer', '2026-01-01', '2026-01-31', 'Netto', 'gt', 100, 'cat-1');

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const calledUrl = mockFetch.mock.calls[0][0];
    expect(calledUrl).toContain('/api/transactions?limit=25&offset=50');
    expect(calledUrl).toContain('filter_type=forbrug');
    expect(calledUrl).toContain('tag=dagligvarer');
    expect(calledUrl).toContain('start_date=2026-01-01');
    expect(calledUrl).toContain('end_date=2026-01-31');
    expect(calledUrl).toContain('search=Netto');
    expect(calledUrl).toContain('amount_op=gt');
    expect(calledUrl).toContain('amount_value=100');
    expect(calledUrl).toContain('category_id=cat-1');
  });

  it('constructs correct query parameters for fetchBudgets', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ budgets: [] }),
    });
    global.fetch = mockFetch;

    await fetchBudgets(2026, 5, 'cat-groceries');
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const calledUrl = mockFetch.mock.calls[0][0];
    expect(calledUrl).toBe('/api/budgets?year=2026&month=5&category_id=cat-groceries');
  });

  it('calls applyBudgetSuggestions endpoint with correct URL and method', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ message: 'Budget suggestions applied successfully', count: 12 }),
    });
    global.fetch = mockFetch;

    const result = await applyBudgetSuggestions(12, 2026);
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe('/api/budgets/apply-suggestions?months=12&year=2026');
    expect(options.method).toBe('POST');
    expect(result.count).toBe(12);
  });
});
