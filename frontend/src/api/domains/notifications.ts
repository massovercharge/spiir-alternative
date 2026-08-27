import { useQuery } from '@tanstack/react-query';
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
