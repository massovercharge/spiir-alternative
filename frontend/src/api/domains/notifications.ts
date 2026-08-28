import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { API_BASE, getHeaders } from '../http';

export interface AppNotification {
  id: string;
  type: 'duplicate_payment' | 'consent_expiring' | 'receipts_linked' | 'rule_suggestion';
  severity: 'warning' | 'danger' | 'info' | 'suggestion';
  title: string;
  message: string;
  created_at: string;
  metadata: Record<string, any>;
  action_type?: 'filter_transactions' | 'navigate' | 'create_rule';
  action_payload?: Record<string, any>;
}

export interface NotificationsResponse {
  count: number;
  notifications: AppNotification[];
}

export interface DuplicatePostingItem {
  id: string;
  account_uid: string;
  account_name: string;
  account_source: string;
  original_description: string;
  amount_minor: number;
  amount: string;
  date: string;
  category_id?: string;
  note?: string;
  split_count: number;
}

export interface DuplicateGroupPreview {
  group_id: string;
  date: string;
  amount_minor: number;
  amount: string;
  description: string;
  can_auto_merge: boolean;
  postings: DuplicatePostingItem[];
}

export interface DuplicatePreviewResponse {
  total_groups: number;
  mergeable_groups_count: number;
  groups: DuplicateGroupPreview[];
}

export function useNotifications() {
  return useQuery<NotificationsResponse>({
    queryKey: ['notifications'],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/api/notifications`, {
        headers: getHeaders(),
      });
      if (!res.ok) throw new Error('Failed to fetch notifications');
      return res.json();
    },
    refetchInterval: 30000, // Poll every 30s
  });
}

export function useDuplicatePreview(enabled = true) {
  return useQuery<DuplicatePreviewResponse>({
    queryKey: ['duplicate-preview'],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/api/notifications/duplicate-preview`, {
        headers: getHeaders(),
      });
      if (!res.ok) throw new Error('Failed to fetch duplicate preview');
      return res.json();
    },
    enabled,
  });
}

export function useResolveDuplicates() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_BASE}/api/notifications/resolve-duplicates`, {
        method: 'POST',
        headers: getHeaders(),
      });
      if (!res.ok) throw new Error('Failed to resolve duplicates');
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
      queryClient.invalidateQueries({ queryKey: ['duplicate-preview'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['accounts'] });
    },
  });
}
