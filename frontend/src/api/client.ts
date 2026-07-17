import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

export const API_BASE = ''; // Proxy handles /api via Vite

let accessToken = '';
let currentHouseholdId = '';

export function setApiToken(token: string) {
  accessToken = token;
}

export function setHouseholdId(id: string) {
  currentHouseholdId = id;
}

export function getHeaders() {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json'
  };
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }
  if (currentHouseholdId) {
    headers['X-Household-Id'] = currentHouseholdId;
  }
  return headers;
}

export async function fetchTransactions(limit = 50, offset = 0, filter_type?: string, tag?: string, start_date?: string, end_date?: string, search?: string, amountOp?: string, amountVal?: number, categoryId?: string) {
  let url = `${API_BASE}/api/transactions?limit=${limit}&offset=${offset}`;
  if (filter_type && filter_type !== 'Alle poster') url += `&filter_type=${encodeURIComponent(filter_type.toLowerCase())}`;
  if (tag) url += `&tag=${encodeURIComponent(tag)}`;
  if (start_date) url += `&start_date=${encodeURIComponent(start_date)}`;
  if (end_date) url += `&end_date=${encodeURIComponent(end_date)}`;
  if (search) url += `&search=${encodeURIComponent(search)}`;
  if (amountOp) url += `&amount_op=${encodeURIComponent(amountOp)}`;
  if (amountVal !== undefined) url += `&amount_value=${amountVal}`;
  if (categoryId) url += `&category_id=${encodeURIComponent(categoryId)}`;
  const res = await fetch(url, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch transactions');
  return res.json();
}

export async function fetchTags() {
  const res = await fetch(`${API_BASE}/api/tags`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch tags');
  return res.json();
}

export async function updateTransactions(transactionIds: string[], patch: any) {
  const res = await fetch(`${API_BASE}/api/transactions`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify({ transaction_ids: transactionIds, patch })
  });
  if (!res.ok) throw new Error('Failed to update transactions');
  return res.json();
}

export async function splitTransaction(transactionId: string, splits: { amount_minor: number; category_id: string | null; note?: string }[]) {
  const res = await fetch(`${API_BASE}/api/transactions/${transactionId}/split`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ splits })
  });
  if (!res.ok) throw new Error('Failed to split transaction');
  return res.json();
}

export async function fetchIncomeExpenseSeries(year?: number) {
  let url = `${API_BASE}/api/insights/income-expense-series`;
  if (year) {
    url += `?year=${year}`;
  }
  const res = await fetch(url, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch income/expense series');
  return res.json();
}

export async function fetchRecurring() {
  const res = await fetch(`${API_BASE}/api/recurring`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch recurring transactions');
  return res.json();
}

export async function fetchAccounts() {
  const res = await fetch(`${API_BASE}/api/accounts`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch accounts');
  return res.json();
}

export async function updateAccount(uid: string, name: string, account_type?: string, savings_category_id?: string | null) {
  const res = await fetch(`${API_BASE}/api/accounts/${uid}`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify({ name, account_type, savings_category_id })
  });
  if (!res.ok) throw new Error('Failed to update account');
  return res.json();
}

export async function fetchAccountBalanceHistory(uid: string, days = 365) {
  const res = await fetch(`${API_BASE}/api/accounts/${uid}/balance_history?days=${days}`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch account balance history');
  return res.json();
}

export async function fetchBudgetsSummary(year: number) {
  const res = await fetch(`${API_BASE}/api/budgets/summary/${year}`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch budgets summary');
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

export async function connectBank(redirectUrl: string) {
  const res = await fetch(`${API_BASE}/api/bank/connect`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ redirect_url: redirectUrl })
  });
  if (!res.ok) throw new Error('Failed to start bank connection');
}

export async function uploadSpiirExport(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return fetchApi('/api/import/spiir', {
    method: 'POST',
    body: formData,
  });
}

export async function uploadStoreboxFile(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return fetchApi('/api/storebox/import-file', {
    method: 'POST',
    body: formData,
  });
}

export async function importStoreboxLink(url: string) {
  return fetchApi('/api/storebox/import-link', {
    method: 'POST',
    body: JSON.stringify({ url }),
  });
}

export async function generateBudgets(months = 12, year?: number) {
  let url = `${API_BASE}/api/budgets/generate?months=${months}`;
  if (year) {
    url += `&year=${year}`;
  }
  const res = await fetch(url, {
    method: 'POST',
    headers: getHeaders()
  });
  if (!res.ok) throw new Error('Failed to generate budgets');
  return res.json();
}

export async function fetchBudgets(year: number, month?: number, categoryId?: string) {
  const params = new URLSearchParams();
  params.append('year', year.toString());
  if (month !== undefined) params.append('month', month.toString());
  if (categoryId) params.append('category_id', categoryId);
  const res = await fetch(`${API_BASE}/api/budgets?${params.toString()}`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch budgets');
  return res.json();
}

export async function upsertBudget(payload: { category_id: string; year: number; month: number; amount_minor: number; budget_type?: string; rollover?: boolean }) {
  const res = await fetch(`${API_BASE}/api/budgets`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error('Failed to upsert budget');
  return res.json();
}

export async function fetchBankConnections() {
  const res = await fetch(`${API_BASE}/api/bank/connections`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch bank connections');
  return res.json();
}

export async function completeBankConnection(code: string) {
  const res = await fetch(`${API_BASE}/api/bank/callback`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ code })
  });
  if (!res.ok) throw new Error('Failed to complete bank connection');
  return res.json();
}

export async function startSync() {
  const res = await fetch(`${API_BASE}/api/sync/start`, {
    method: 'POST',
    headers: getHeaders()
  });
  if (!res.ok) throw new Error('Failed to start sync');
  return res.json();
}

export async function getSyncStatus() {
  const res = await fetch(`${API_BASE}/api/sync/status`, {
    headers: getHeaders()
  });
  if (!res.ok) throw new Error('Failed to fetch sync status');
  return res.json();
}

export async function updateTransactionCategory(transactionId: string, categoryId: string) {
  const res = await fetch(`${API_BASE}/api/transactions/${transactionId}/category`, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify({ category_id: categoryId })
  });
  if (!res.ok) throw new Error('Failed to update category');
  return res.json();
}

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

// Households

export async function fetchHouseholds() {
  const res = await fetch(`${API_BASE}/api/households`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch households');
  return res.json();
}

export async function createHousehold(name: string) {
  const res = await fetch(`${API_BASE}/api/households`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ name })
  });
  if (!res.ok) throw new Error('Failed to create household');
  return res.json();
}

export async function fetchHouseholdMembers(householdId: string) {
  const res = await fetch(`${API_BASE}/api/households/${householdId}/members`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch household members');
  return res.json();
}

export async function inviteHouseholdMember(householdId: string, email: string) {
  const res = await fetch(`${API_BASE}/api/households/${householdId}/members`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ email })
  });
  if (!res.ok) throw new Error('Failed to invite household member');
  return res.json();
}

// Hooks

export interface Account {
  uid: string;
  name: string;
  iban: string | null;
  currency: string;
  source: string;
  account_type: string;
  savings_category_id?: string | null;
  balance: string;
  balance_minor: number;
  bank_connection: {
    id: string;
    provider: string;
    bank_name: string;
    status: string;
  } | null;
}

export function useTransactions(limit = 50, offset = 0, filter_type?: string, tag?: string, start_date?: string, end_date?: string, search?: string, amountOp?: string, amountVal?: number, categoryId?: string) {
  return useQuery({
    queryKey: ['transactions', limit, offset, filter_type, tag, start_date, end_date, search, amountOp, amountVal, categoryId],
    queryFn: () => fetchTransactions(limit, offset, filter_type, tag, start_date, end_date, search, amountOp, amountVal, categoryId),
  });
}

export function useTags() {
  return useQuery({
    queryKey: ['tags'],
    queryFn: fetchTags,
  });
}

export function useUpdateTransactions() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ transactionIds, patch }: { transactionIds: string[], patch: any }) => 
      updateTransactions(transactionIds, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['insights-sunburst'] });
      queryClient.invalidateQueries({ queryKey: ['budgets-summary'] });
    }
  });
}

export function useSplitTransaction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ transactionId, splits }: { transactionId: string, splits: { amount_minor: number; category_id: string | null; note?: string }[] }) => 
      splitTransaction(transactionId, splits),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['insights-sunburst'] });
      queryClient.invalidateQueries({ queryKey: ['budgets-summary'] });
    }
  });
}

export function useIncomeExpenseSeries(year?: number) {
  return useQuery({
    queryKey: ['insights', 'income-expense-series', year],
    queryFn: () => fetchIncomeExpenseSeries(year),
  });
}

export function useBudgets(year: number, categoryId?: string) {
  return useQuery({
    queryKey: ['budgets', year, categoryId],
    queryFn: () => fetchBudgets(year, undefined, categoryId),
  });
}

export function useUpsertBudget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Parameters<typeof upsertBudget>[0]) => upsertBudget(payload),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['budgets', variables.year] });
      queryClient.invalidateQueries({ queryKey: ['budgets-summary', variables.year] });
    }
  });
}

export function useRecurring() {
  return useQuery({
    queryKey: ['recurring'],
    queryFn: fetchRecurring,
  });
}

export function useAccounts() {
  return useQuery({
    queryKey: ['accounts'],
    queryFn: fetchAccounts,
  });
}

export function useAccountBalanceHistory(uid: string, days = 365) {
  return useQuery({
    queryKey: ['accounts', uid, 'history', days],
    queryFn: () => fetchAccountBalanceHistory(uid, days),
    enabled: !!uid,
  });
}

export function useUpdateAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ uid, name, account_type, savings_category_id }: { uid: string; name: string; account_type?: string; savings_category_id?: string | null }) => 
      updateAccount(uid, name, account_type, savings_category_id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts'] });
    }
  });
}



export function useBudgetsSummary(year: number) {
  return useQuery({
    queryKey: ['budgets-summary', year],
    queryFn: () => fetchBudgetsSummary(year),
  });
}

export function useInsightsSunburst(params: { year?: number; month?: number; filterType?: string; startDate?: string; endDate?: string } = {}) {
  return useQuery({
    queryKey: ['insights', 'sunburst', params.year, params.month, params.filterType, params.startDate, params.endDate],
    queryFn: () => fetchInsightsSunburst(params),
  });
}

export function useInsightsAverages(year: number) {
  return useQuery({
    queryKey: ['insights', 'averages', year],
    queryFn: () => fetchInsightsAverages(year),
    enabled: !!year,
  });
}

export function useCategoryDrilldown(categoryName: string | null, year: number) {
  return useQuery({
    queryKey: ['insights', 'category-drilldown', categoryName, year],
    queryFn: () => fetchCategoryDrilldown(categoryName!, year),
    enabled: !!categoryName,
  });
}

export function useGenerateBudgets() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ months, year }: { months?: number, year?: number } = {}) => generateBudgets(months, year),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['budgets-summary'] });
    }
  });
}

export async function fetchBudgetBills(categoryId: string, year: number) {
  const res = await fetch(`${API_BASE}/api/budgets/bills/${categoryId}/${year}`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch budget bills');
  return res.json();
}

export async function upsertBudgetBills(payload: { category_id: string; year: number; bills: any[] }) {
  const res = await fetch(`${API_BASE}/api/budgets/bills`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error('Failed to upsert budget bills');
  return res.json();
}

export function useBudgetBills(categoryId: string | null, year: number) {
  return useQuery({
    queryKey: ['budget-bills', categoryId, year],
    queryFn: () => fetchBudgetBills(categoryId!, year),
    enabled: !!categoryId,
  });
}

export function useSaveBudgetBills() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: upsertBudgetBills,
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['budget-bills', variables.category_id, variables.year] });
      queryClient.invalidateQueries({ queryKey: ['budgets-summary'] });
    }
  });
}

export function useUploadSpiirExport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => uploadSpiirExport(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['insights-sunburst'] });
      queryClient.invalidateQueries({ queryKey: ['budgets-summary'] });
    }
  });
}

export function useUploadStoreboxFile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => uploadStoreboxFile(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['insights-sunburst'] });
      queryClient.invalidateQueries({ queryKey: ['budgets-summary'] });
    }
  });
}

export function useImportStoreboxLink() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (url: string) => importStoreboxLink(url),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['insights-sunburst'] });
      queryClient.invalidateQueries({ queryKey: ['budgets-summary'] });
    }
  });
}

export function useConnectBank() {
  return useMutation({
    mutationFn: (redirectUrl: string) => connectBank(redirectUrl),
  });
}

export function useBankConnections() {
  return useQuery({
    queryKey: ['bank-connections'],
    queryFn: fetchBankConnections,
  });
}

export function useCompleteBankConnection() {
  return useMutation({
    mutationFn: (code: string) => completeBankConnection(code),
  });
}

export function useStartSync() {
  return useMutation({
    mutationFn: () => startSync(),
  });
}

export function useSyncStatus(isPolling: boolean) {
  return useQuery({
    queryKey: ['syncStatus'],
    queryFn: () => getSyncStatus(),
    refetchInterval: isPolling ? 2000 : false, // Poll every 2 seconds if isPolling is true
    enabled: isPolling,
  });
}

export function useUpdateTransactionCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ transactionId, categoryId }: { transactionId: string, categoryId: string }) => 
      updateTransactionCategory(transactionId, categoryId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['insights-sunburst'] });
      queryClient.invalidateQueries({ queryKey: ['budgets-summary'] });
    }
  });
}

export function useCreateCustomRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ matchPattern, categoryId }: { matchPattern: string, categoryId: string }) => 
      createCustomRule(matchPattern, categoryId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['insights-sunburst'] });
      queryClient.invalidateQueries({ queryKey: ['rules'] });
      queryClient.invalidateQueries({ queryKey: ['budgets-summary'] });
    }
  });
}

export function useRules(source?: string) {
  return useQuery({
    queryKey: ['rules', source],
    queryFn: () => fetchRules(source),
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

// Household Hooks

export function useHouseholds() {
  return useQuery({
    queryKey: ['households'],
    queryFn: fetchHouseholds,
  });
}

export function useCreateHousehold() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => createHousehold(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['households'] });
    }
  });
}

export function useHouseholdMembers(householdId: string) {
  return useQuery({
    queryKey: ['households', householdId, 'members'],
    queryFn: () => fetchHouseholdMembers(householdId),
    enabled: !!householdId,
  });
}

export function useInviteHouseholdMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ householdId, email }: { householdId: string, email: string }) => inviteHouseholdMember(householdId, email),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['households', variables.householdId, 'members'] });
    }
  });
}
