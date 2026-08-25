import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { API_BASE, getHeaders, getHouseholdId } from '../http';
import type { SuggestedReceipt } from '../types';

export async function fetchTransactions(
  limit = 50,
  offset = 0,
  filter_type?: string,
  tag?: string,
  start_date?: string,
  end_date?: string,
  search?: string,
  amountOp?: string,
  amountVal?: number,
  categoryId?: string
) {
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

export async function linkReceiptToTransaction(transactionId: string, receiptId: string) {
  const res = await fetch(`${API_BASE}/api/transactions/${transactionId}/link-receipt`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ receipt_id: receiptId })
  });
  if (!res.ok) throw new Error('Failed to link receipt to transaction');
  return res.json();
}

export async function fetchSuggestedReceipts(transactionId: string): Promise<SuggestedReceipt[]> {
  const res = await fetch(`${API_BASE}/api/transactions/${transactionId}/suggested-receipts`, {
    headers: getHeaders()
  });
  if (!res.ok) throw new Error('Failed to fetch suggested receipts');
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

export function useTransactions(
  limit = 50,
  offset = 0,
  filter_type?: string,
  tag?: string,
  start_date?: string,
  end_date?: string,
  search?: string,
  amountOp?: string,
  amountVal?: number,
  categoryId?: string
) {
  const currentHouseholdId = getHouseholdId();
  return useQuery({
    queryKey: ['transactions', currentHouseholdId, limit, offset, filter_type, tag, start_date, end_date, search, amountOp, amountVal, categoryId],
    queryFn: () => fetchTransactions(limit, offset, filter_type, tag, start_date, end_date, search, amountOp, amountVal, categoryId),
  });
}

export function useTags() {
  const currentHouseholdId = getHouseholdId();
  return useQuery({
    queryKey: ['tags', currentHouseholdId],
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
      queryClient.invalidateQueries({ queryKey: ['insights'] });
      queryClient.invalidateQueries({ queryKey: ['budgets'] });
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
      queryClient.invalidateQueries({ queryKey: ['insights'] });
      queryClient.invalidateQueries({ queryKey: ['budgets'] });
      queryClient.invalidateQueries({ queryKey: ['budgets-summary'] });
    }
  });
}

export function useLinkReceiptToTransaction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ transactionId, receiptId }: { transactionId: string, receiptId: string }) => 
      linkReceiptToTransaction(transactionId, receiptId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['insights'] });
      queryClient.invalidateQueries({ queryKey: ['budgets'] });
      queryClient.invalidateQueries({ queryKey: ['budgets-summary'] });
      queryClient.invalidateQueries({ queryKey: ['suggested-receipts'] });
    }
  });
}

export function useSuggestedReceipts(transactionId: string | null | undefined, enabled = true) {
  const currentHouseholdId = getHouseholdId();
  return useQuery<SuggestedReceipt[]>({
    queryKey: ['suggested-receipts', transactionId, currentHouseholdId],
    queryFn: () => fetchSuggestedReceipts(transactionId!),
    enabled: Boolean(transactionId) && enabled,
    staleTime: 60 * 1000,
  });
}

export function useUpdateTransactionCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ transactionId, categoryId }: { transactionId: string, categoryId: string }) => 
      updateTransactionCategory(transactionId, categoryId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['insights'] });
      queryClient.invalidateQueries({ queryKey: ['budgets'] });
      queryClient.invalidateQueries({ queryKey: ['budgets-summary'] });
    }
  });
}
