import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { API_BASE, getHeaders, getHouseholdId } from '../http';
import type { BudgetsSummary } from '../types';

export async function fetchBudgetsSummary(year: number): Promise<BudgetsSummary> {
  const res = await fetch(`${API_BASE}/api/budgets/summary/${year}`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch budgets summary');
  return res.json();
}

export async function fetchBudgets(year: number, month?: number, categoryId?: string) {
  const params = new URLSearchParams();
  params.append('year', year.toString());
  if (month !== undefined) params.append('month', month.toString());
  if (categoryId) params.append('category_id', categoryId);
  const res = await fetch(`${API_BASE}/api/budgets?${params.toString()}`, {
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error('Failed to fetch budgets');
  return res.json();
}

export async function upsertBudget(payload: {
  category_id: string;
  year: number;
  month: number;
  amount_minor: number;
  budget_type?: string;
  rollover?: boolean;
}) {
  const res = await fetch(`${API_BASE}/api/budgets`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to upsert budget');
  return res.json();
}

export async function generateBudgets(months = 12, year?: number) {
  let url = `${API_BASE}/api/budgets/generate?months=${months}`;
  if (year) {
    url += `&year=${year}`;
  }
  const res = await fetch(url, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error('Failed to generate budgets');
  return res.json();
}

export async function applyBudgetSuggestions(months = 12, year?: number) {
  let url = `${API_BASE}/api/budgets/apply-suggestions?months=${months}`;
  if (year) {
    url += `&year=${year}`;
  }
  const res = await fetch(url, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error('Failed to apply budget suggestions');
  return res.json();
}

export async function fetchBudgetBills(categoryId: string, year: number) {
  const res = await fetch(`${API_BASE}/api/budgets/bills/${categoryId}/${year}`, {
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error('Failed to fetch budget bills');
  return res.json();
}

export async function upsertBudgetBills(payload: {
  category_id: string;
  year: number;
  bills: any[];
}) {
  const res = await fetch(`${API_BASE}/api/budgets/bills`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to upsert budget bills');
  return res.json();
}

export function useBudgets(year: number, categoryId?: string) {
  const currentHouseholdId = getHouseholdId();
  return useQuery({
    queryKey: ['budgets', currentHouseholdId, year, categoryId],
    queryFn: () => fetchBudgets(year, undefined, categoryId),
  });
}

export function useUpsertBudget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Parameters<typeof upsertBudget>[0]) => upsertBudget(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['budgets'] });
      queryClient.invalidateQueries({ queryKey: ['budgets-summary'] });
    },
  });
}

export function useBudgetsSummary(year: number) {
  const currentHouseholdId = getHouseholdId();
  return useQuery<BudgetsSummary>({
    queryKey: ['budgets-summary', currentHouseholdId, year],
    queryFn: () => fetchBudgetsSummary(year),
  });
}

export function useGenerateBudgets() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ months, year }: { months?: number; year?: number } = {}) =>
      generateBudgets(months, year),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['budgets-summary'] });
    },
  });
}

export function useApplyBudgetSuggestions() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ months, year }: { months?: number; year?: number } = {}) =>
      applyBudgetSuggestions(months, year),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['budgets'] });
      queryClient.invalidateQueries({ queryKey: ['budgets-summary'] });
    },
  });
}

export function useBudgetBills(categoryId: string | null, year: number) {
  const currentHouseholdId = getHouseholdId();
  return useQuery({
    queryKey: ['budget-bills', currentHouseholdId, categoryId, year],
    queryFn: () => fetchBudgetBills(categoryId!, year),
    enabled: !!categoryId,
  });
}

export function useSaveBudgetBills() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: upsertBudgetBills,
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['budget-bills', variables.category_id, variables.year],
      });
      queryClient.invalidateQueries({ queryKey: ['budgets'] });
      queryClient.invalidateQueries({ queryKey: ['budgets-summary'] });
    },
  });
}
