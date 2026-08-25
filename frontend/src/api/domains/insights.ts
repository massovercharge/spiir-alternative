import { useQuery } from '@tanstack/react-query';
import { API_BASE, getHeaders, getHouseholdId } from '../http';

export async function fetchIncomeExpenseSeries(year?: number) {
  let url = `${API_BASE}/api/insights/income-expense-series`;
  if (year) {
    url += `?year=${year}`;
  }
  const res = await fetch(url, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch income/expense series');
  return res.json();
}

export async function fetchCategoryDrilldown(categoryName: string, year: number) {
  const res = await fetch(`${API_BASE}/api/insights/category-drilldown?category_name=${encodeURIComponent(categoryName)}&year=${year}`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch category drilldown');
  return res.json();
}

export async function fetchInsightsSunburst(params: { year?: number; month?: number; filterType?: string; startDate?: string; endDate?: string } = {}) {
  const url = new URL(`${API_BASE}/api/insights/sunburst`, window.location.origin);
  if (params.year) url.searchParams.append('year', params.year.toString());
  if (params.month) url.searchParams.append('month', params.month.toString());
  if (params.filterType) url.searchParams.append('filter_type', params.filterType);
  if (params.startDate) url.searchParams.append('start_date', params.startDate);
  if (params.endDate) url.searchParams.append('end_date', params.endDate);
  const res = await fetch(url.toString(), { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch insights sunburst');
  return res.json();
}

export async function fetchInsightsAverages(year: number) {
  const res = await fetch(`${API_BASE}/api/insights/averages?year=${year}`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch insights averages');
  return res.json();
}

export function useIncomeExpenseSeries(year?: number) {
  const currentHouseholdId = getHouseholdId();
  return useQuery({
    queryKey: ['insights', 'income-expense-series', currentHouseholdId, year],
    queryFn: () => fetchIncomeExpenseSeries(year),
  });
}

export function useInsightsSunburst(params: { year?: number; month?: number; filterType?: string; startDate?: string; endDate?: string } = {}) {
  const currentHouseholdId = getHouseholdId();
  return useQuery({
    queryKey: ['insights', 'sunburst', currentHouseholdId, params.year, params.month, params.filterType, params.startDate, params.endDate],
    queryFn: () => fetchInsightsSunburst(params),
  });
}

export function useInsightsAverages(year: number) {
  const currentHouseholdId = getHouseholdId();
  return useQuery({
    queryKey: ['insights', 'averages', currentHouseholdId, year],
    queryFn: () => fetchInsightsAverages(year),
    enabled: !!year,
  });
}

export function useCategoryDrilldown(categoryName: string | null, year: number) {
  const currentHouseholdId = getHouseholdId();
  return useQuery({
    queryKey: ['insights', 'category-drilldown', currentHouseholdId, categoryName, year],
    queryFn: () => fetchCategoryDrilldown(categoryName!, year),
    enabled: !!categoryName,
  });
}
