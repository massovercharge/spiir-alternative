import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { API_BASE, getHeaders, getHouseholdId } from '../http';

export async function createCustomRule(matchPattern: string, categoryId: string) {
  const res = await fetch(`${API_BASE}/api/rules/custom`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ match_pattern: matchPattern, category_id: categoryId })
  });
  if (!res.ok) throw new Error('Failed to create custom rule');
  return res.json();
}

export async function fetchRules(source?: string) {
  const url = source ? `${API_BASE}/api/rules?source=${source}` : `${API_BASE}/api/rules`;
  const res = await fetch(url, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch rules');
  return res.json();
}

export async function deleteRule(ruleId: string) {
  const res = await fetch(`${API_BASE}/api/rules/${ruleId}`, {
    method: 'DELETE',
    headers: getHeaders()
  });
  if (!res.ok) throw new Error('Failed to delete rule');
  return res.json();
}

export function useRules(source?: string) {
  const currentHouseholdId = getHouseholdId();
  return useQuery({
    queryKey: ['rules', currentHouseholdId, source],
    queryFn: () => fetchRules(source),
  });
}

export function useCreateCustomRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ matchPattern, categoryId }: { matchPattern: string, categoryId: string }) => 
      createCustomRule(matchPattern, categoryId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['insights'] });
      queryClient.invalidateQueries({ queryKey: ['rules'] });
      queryClient.invalidateQueries({ queryKey: ['budgets'] });
      queryClient.invalidateQueries({ queryKey: ['budgets-summary'] });
    }
  });
}

export function useDeleteRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ruleId: string) => deleteRule(ruleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules'] });
    }
  });
}
