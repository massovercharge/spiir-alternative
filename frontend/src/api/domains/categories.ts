import { useQuery } from '@tanstack/react-query';
import { API_BASE, getHeaders, getHouseholdId } from '../http';

export async function fetchCategories() {
  const res = await fetch(`${API_BASE}/api/categories`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch categories');
  return res.json();
}

export async function fetchRecurring() {
  const res = await fetch(`${API_BASE}/api/recurring`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch recurring transactions');
  return res.json();
}

export function useCategories() {
  const currentHouseholdId = getHouseholdId();
  return useQuery({
    queryKey: ['categories', currentHouseholdId],
    queryFn: fetchCategories,
  });
}

export function useRecurring() {
  const currentHouseholdId = getHouseholdId();
  return useQuery({
    queryKey: ['recurring', currentHouseholdId],
    queryFn: fetchRecurring,
  });
}
