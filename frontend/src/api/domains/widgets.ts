import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { API_BASE, getHeaders, getHouseholdId } from '../http';
import {
  ActiveWidgetData,
  WidgetListItem,
  WidgetManifest,
  WidgetOutput,
} from '../../features/widgets/types';

export async function fetchWidgets(householdId?: string): Promise<WidgetListItem[]> {
  const hId = householdId || getHouseholdId();
  let url = `${API_BASE}/api/widgets`;
  if (hId) {
    url += `?household_id=${encodeURIComponent(hId)}`;
  }
  const res = await fetch(url, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch widgets');
  return res.json();
}

export async function toggleWidgetApi(
  widgetId: string,
  enabled: boolean,
  householdId?: string
): Promise<{ widget_id: string; is_enabled: boolean }> {
  const hId = householdId || getHouseholdId();
  let url = `${API_BASE}/api/widgets/${encodeURIComponent(widgetId)}/toggle`;
  if (hId) {
    url += `?household_id=${encodeURIComponent(hId)}`;
  }
  const res = await fetch(url, {
    method: 'POST',
    headers: { ...getHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  });
  if (!res.ok) throw new Error('Failed to toggle widget');
  return res.json();
}

export async function reorderWidgetApi(
  widgetId: string,
  direction: 'up' | 'down',
  householdId?: string
): Promise<{ order: string[] }> {
  const hId = householdId || getHouseholdId();
  let url = `${API_BASE}/api/widgets/${encodeURIComponent(widgetId)}/reorder`;
  if (hId) {
    url += `?household_id=${encodeURIComponent(hId)}`;
  }
  const res = await fetch(url, {
    method: 'POST',
    headers: { ...getHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ direction }),
  });
  if (!res.ok) throw new Error('Failed to reorder widget');
  return res.json();
}

export async function fetchSingleWidgetData(
  widgetId: string,
  forceRefresh = false,
  householdId?: string
): Promise<{ manifest: WidgetManifest; output: WidgetOutput }> {
  const hId = householdId || getHouseholdId();
  let url = `${API_BASE}/api/widgets/${encodeURIComponent(widgetId)}/data?force_refresh=${forceRefresh}`;
  if (hId) {
    url += `&household_id=${encodeURIComponent(hId)}`;
  }
  const res = await fetch(url, { headers: getHeaders() });
  if (!res.ok) throw new Error(`Failed to fetch widget data for ${widgetId}`);
  return res.json();
}

export async function fetchActiveWidgetsData(
  forceRefresh = false,
  householdId?: string
): Promise<ActiveWidgetData[]> {
  const hId = householdId || getHouseholdId();
  let url = `${API_BASE}/api/widgets/active/data?force_refresh=${forceRefresh}`;
  if (hId) {
    url += `&household_id=${encodeURIComponent(hId)}`;
  }
  const res = await fetch(url, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch active widgets data');
  return res.json();
}

export async function reloadWidgetsApi(): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API_BASE}/api/widgets/reload`, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error('Failed to reload widgets');
  return res.json();
}

// React Query Hooks

export function useWidgets() {
  const currentHouseholdId = getHouseholdId();
  return useQuery({
    queryKey: ['widgets', 'list', currentHouseholdId],
    queryFn: () => fetchWidgets(currentHouseholdId),
  });
}

export function useActiveWidgetsData() {
  const currentHouseholdId = getHouseholdId();
  return useQuery({
    queryKey: ['widgets', 'active-data', currentHouseholdId],
    queryFn: () => fetchActiveWidgetsData(false, currentHouseholdId),
  });
}

export function useToggleWidget() {
  const queryClient = useQueryClient();
  const currentHouseholdId = getHouseholdId();

  return useMutation({
    mutationFn: ({ widgetId, enabled }: { widgetId: string; enabled: boolean }) =>
      toggleWidgetApi(widgetId, enabled, currentHouseholdId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['widgets', 'list'] });
      queryClient.invalidateQueries({ queryKey: ['widgets', 'active-data'] });
    },
  });
}

export function useReorderWidget() {
  const queryClient = useQueryClient();
  const currentHouseholdId = getHouseholdId();

  return useMutation({
    mutationFn: ({ widgetId, direction }: { widgetId: string; direction: 'up' | 'down' }) =>
      reorderWidgetApi(widgetId, direction, currentHouseholdId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['widgets', 'list'] });
      queryClient.invalidateQueries({ queryKey: ['widgets', 'active-data'] });
    },
  });
}

export function useReloadWidgets() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: reloadWidgetsApi,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['widgets'] });
    },
  });
}
