import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { API_BASE, getHeaders } from '../http';
import type { InboundConfig, InboundEmailLog, ReceiptsStatus } from '../types';

export async function fetchInboundConfig(householdId: string): Promise<InboundConfig> {
  const res = await fetch(`${API_BASE}/api/households/${householdId}/inbound-config`, {
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error('Failed to fetch inbound email config');
  return res.json();
}

export async function regenerateInboundToken(householdId: string): Promise<InboundConfig> {
  const res = await fetch(
    `${API_BASE}/api/households/${householdId}/inbound-config/regenerate-token`,
    {
      method: 'POST',
      headers: getHeaders(),
    }
  );
  if (!res.ok) throw new Error('Failed to regenerate inbound token');
  return res.json();
}

export async function fetchInboundEmails(householdId: string): Promise<InboundEmailLog[]> {
  const res = await fetch(`${API_BASE}/api/households/${householdId}/inbound-emails`, {
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error('Failed to fetch inbound emails');
  return res.json();
}

export async function simulateInboundEmail(
  householdId: string,
  payload: { raw_content?: string; url?: string; subject?: string; sender?: string }
) {
  const res = await fetch(`${API_BASE}/api/households/${householdId}/inbound-emails/test`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to simulate inbound email');
  return res.json();
}

export async function retryInboundEmail(householdId: string, emailId: string) {
  const res = await fetch(
    `${API_BASE}/api/households/${householdId}/inbound-emails/${emailId}/retry`,
    {
      method: 'POST',
      headers: getHeaders(),
    }
  );
  if (!res.ok) throw new Error('Failed to retry inbound email');
  return res.json();
}

export async function deleteInboundEmail(householdId: string, emailId: string) {
  const res = await fetch(`${API_BASE}/api/households/${householdId}/inbound-emails/${emailId}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error('Failed to delete inbound email log');
  return res.json();
}

export async function clearInboundEmails(householdId: string) {
  const res = await fetch(`${API_BASE}/api/households/${householdId}/inbound-emails`, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error('Failed to clear inbound emails');
  return res.json();
}

export async function uploadStoreboxFile(file: File) {
  const formData = new FormData();
  formData.append('file', file);

  const headers = getHeaders();
  delete headers['Content-Type'];

  const res = await fetch(`${API_BASE}/api/storebox/import-file`, {
    method: 'POST',
    headers,
    body: formData,
  });
  if (!res.ok) throw new Error('Failed to upload Storebox file');
  return res.json();
}

export async function uploadCoopFile(file: File) {
  const formData = new FormData();
  formData.append('file', file);

  const headers = getHeaders();
  delete headers['Content-Type'];

  const res = await fetch(`${API_BASE}/api/coop/import-file`, {
    method: 'POST',
    headers,
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to upload Coop file');
  }
  return res.json();
}

export async function importStoreboxLink(url: string) {
  const res = await fetch(`${API_BASE}/api/storebox/import-link`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ url }),
  });
  if (!res.ok) throw new Error('Failed to import from link');
  return res.json();
}

export function useInboundConfig(householdId: string | null | undefined) {
  return useQuery({
    queryKey: ['households', householdId, 'inbound-config'],
    queryFn: () => fetchInboundConfig(householdId!),
    enabled: !!householdId,
  });
}

export function useInboundEmails(householdId: string | null | undefined) {
  return useQuery({
    queryKey: ['households', householdId, 'inbound-emails'],
    queryFn: () => fetchInboundEmails(householdId!),
    enabled: !!householdId,
    refetchInterval: 15000,
  });
}

export function useRegenerateInboundToken() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (householdId: string) => regenerateInboundToken(householdId),
    onSuccess: (_, householdId) => {
      queryClient.invalidateQueries({ queryKey: ['households', householdId, 'inbound-config'] });
    },
  });
}

export function useSimulateInboundEmail() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      householdId,
      payload,
    }: {
      householdId: string;
      payload: { raw_content?: string; url?: string; subject?: string; sender?: string };
    }) => simulateInboundEmail(householdId, payload),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['households', variables.householdId, 'inbound-emails'],
      });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['insights'] });
    },
  });
}

export function useRetryInboundEmail() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ householdId, emailId }: { householdId: string; emailId: string }) =>
      retryInboundEmail(householdId, emailId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['households', variables.householdId, 'inbound-emails'],
      });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['insights'] });
    },
  });
}

export function useDeleteInboundEmail() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ householdId, emailId }: { householdId: string; emailId: string }) =>
      deleteInboundEmail(householdId, emailId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['households', variables.householdId, 'inbound-emails'],
      });
    },
  });
}

export function useClearInboundEmails() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (householdId: string) => clearInboundEmails(householdId),
    onSuccess: (_, householdId) => {
      queryClient.invalidateQueries({ queryKey: ['households', householdId, 'inbound-emails'] });
    },
  });
}

export async function fetchReceiptsStatus(): Promise<ReceiptsStatus> {
  const res = await fetch(`${API_BASE}/api/receipts/status`, {
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error('Failed to fetch receipts status');
  return res.json();
}

export function useReceiptsStatus() {
  return useQuery({
    queryKey: ['receipts-status'],
    queryFn: fetchReceiptsStatus,
    refetchInterval: 10000,
  });
}

export function useUploadStoreboxFile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => uploadStoreboxFile(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['receipts-status'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['insights'] });
      queryClient.invalidateQueries({ queryKey: ['budgets'] });
      queryClient.invalidateQueries({ queryKey: ['budgets-summary'] });
    },
  });
}

export function useImportStoreboxLink() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (url: string) => importStoreboxLink(url),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['receipts-status'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['insights'] });
      queryClient.invalidateQueries({ queryKey: ['budgets'] });
      queryClient.invalidateQueries({ queryKey: ['budgets-summary'] });
    },
  });
}

export function useUploadCoopFile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => uploadCoopFile(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['receipts-status'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['insights'] });
      queryClient.invalidateQueries({ queryKey: ['budgets'] });
      queryClient.invalidateQueries({ queryKey: ['budgets-summary'] });
    },
  });
}

export async function autoLinkReceipts(): Promise<{ auto_linked_count: number; status: ReceiptsStatus }> {
  const res = await fetch(`${API_BASE}/api/receipts/auto-link`, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error('Failed to auto-link receipts');
  return res.json();
}

export function useAutoLinkReceipts() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: autoLinkReceipts,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['receipts-status'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['insights'] });
      queryClient.invalidateQueries({ queryKey: ['budgets'] });
      queryClient.invalidateQueries({ queryKey: ['budgets-summary'] });
    },
  });
}

