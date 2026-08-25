import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { API_BASE, getHeaders, getHouseholdId } from '../http';

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

export async function connectBank(redirectUrl: string, bankName: string) {
  const res = await fetch(`${API_BASE}/api/bank/connect`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ redirect_url: redirectUrl, bank_name: bankName })
  });
  if (!res.ok) throw new Error('Failed to start bank connection');
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

export async function deleteBankConnection(connectionId: string) {
  const res = await fetch(`${API_BASE}/api/bank/connections/${connectionId}`, {
    method: 'DELETE',
    headers: getHeaders()
  });
  if (!res.ok) throw new Error('Failed to delete bank connection');
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

export async function uploadSpiirExport(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  
  const headers = getHeaders();
  delete headers['Content-Type']; // Let browser set multipart/form-data boundary

  const res = await fetch(`${API_BASE}/api/import/spiir`, {
    method: 'POST',
    headers,
    body: formData,
  });
  if (!res.ok) throw new Error('Failed to upload file');
  return res.json();
}

export function useAccounts() {
  const currentHouseholdId = getHouseholdId();
  return useQuery({
    queryKey: ['accounts', currentHouseholdId],
    queryFn: fetchAccounts,
  });
}

export function useAccountBalanceHistory(uid: string, days = 365) {
  const currentHouseholdId = getHouseholdId();
  return useQuery({
    queryKey: ['accounts', currentHouseholdId, uid, 'history', days],
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

export function useBankConnections() {
  const currentHouseholdId = getHouseholdId();
  return useQuery({
    queryKey: ['bank-connections', currentHouseholdId],
    queryFn: fetchBankConnections,
  });
}

export function useConnectBank() {
  return useMutation({
    mutationFn: ({ redirectUrl, bankName }: { redirectUrl: string; bankName: string }) => connectBank(redirectUrl, bankName),
  });
}

export function useCompleteBankConnection() {
  return useMutation({
    mutationFn: (code: string) => completeBankConnection(code),
  });
}

export function useDeleteBankConnection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (connectionId: string) => deleteBankConnection(connectionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bank-connections'] });
      queryClient.invalidateQueries({ queryKey: ['accounts'] });
    }
  });
}

export function useStartSync() {
  return useMutation({
    mutationFn: () => startSync(),
  });
}

export function useSyncStatus(isPolling: boolean) {
  const currentHouseholdId = getHouseholdId();
  return useQuery({
    queryKey: ['syncStatus', currentHouseholdId],
    queryFn: () => getSyncStatus(),
    refetchInterval: isPolling ? 2000 : false,
    enabled: isPolling,
  });
}

export function useUploadSpiirExport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => uploadSpiirExport(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['insights'] });
      queryClient.invalidateQueries({ queryKey: ['budgets'] });
      queryClient.invalidateQueries({ queryKey: ['budgets-summary'] });
    }
  });
}
