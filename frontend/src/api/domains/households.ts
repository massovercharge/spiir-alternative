import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { API_BASE, getHeaders } from '../http';

export async function fetchHouseholds() {
  const res = await fetch(`${API_BASE}/api/households`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch households');
  return res.json();
}

export async function createHousehold(name: string) {
  const res = await fetch(`${API_BASE}/api/households`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error('Failed to create household');
  return res.json();
}

export async function updateHousehold(householdId: string, name: string) {
  const res = await fetch(`${API_BASE}/api/households/${householdId}`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify({ name }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to update household');
  }
  return res.json();
}

export async function fetchHouseholdMembers(householdId: string) {
  const res = await fetch(`${API_BASE}/api/households/${householdId}/members`, {
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error('Failed to fetch household members');
  return res.json();
}

export async function inviteHouseholdMember(
  householdId: string,
  email: string,
  role: string = 'member'
) {
  const res = await fetch(`${API_BASE}/api/households/${householdId}/members`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ email, role }),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to invite member');
  }
  return res.json();
}

export async function removeHouseholdMember(householdId: string, userId: string) {
  const res = await fetch(`${API_BASE}/api/households/${householdId}/members/${userId}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to remove member');
  }
  return res.json();
}

export async function updateHouseholdMemberRole(householdId: string, userId: string, role: string) {
  const res = await fetch(`${API_BASE}/api/households/${householdId}/members/${userId}/role`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify({ role }),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to update member role');
  }
  return res.json();
}

export async function deleteHousehold(householdId: string) {
  const res = await fetch(`${API_BASE}/api/households/${householdId}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to delete household');
  }
  return res.json();
}

export async function restoreHousehold(householdId: string) {
  const res = await fetch(`${API_BASE}/api/households/${householdId}/restore`, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to restore household');
  }
  return res.json();
}

export function useHouseholds() {
  return useQuery({
    queryKey: ['households'],
    queryFn: fetchHouseholds,
    staleTime: 0,
    refetchOnMount: true,
  });
}

export function useCreateHousehold() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => createHousehold(name),
    onSuccess: (newHousehold) => {
      queryClient.setQueryData(['households'], (oldData: any[] | undefined) => {
        const list = oldData || [];
        if (list.some((h: any) => h.id === newHousehold.id)) return list;
        return [...list, newHousehold];
      });
      queryClient.invalidateQueries({ queryKey: ['households'] });
    },
  });
}

export function useUpdateHousehold() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ householdId, name }: { householdId: string; name: string }) =>
      updateHousehold(householdId, name),
    onSuccess: (updated) => {
      queryClient.setQueryData(['households'], (oldData: any[] | undefined) => {
        const list = oldData || [];
        return list.map((h: any) => (h.id === updated.id ? { ...h, name: updated.name } : h));
      });
      queryClient.invalidateQueries({ queryKey: ['households'] });
    },
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
    mutationFn: ({
      householdId,
      email,
      role = 'member',
    }: {
      householdId: string;
      email: string;
      role?: string;
    }) => inviteHouseholdMember(householdId, email, role),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['households', variables.householdId, 'members'] });
    },
  });
}

export function useUpdateHouseholdMemberRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      householdId,
      userId,
      role,
    }: {
      householdId: string;
      userId: string;
      role: string;
    }) => updateHouseholdMemberRole(householdId, userId, role),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['households', variables.householdId, 'members'] });
      queryClient.invalidateQueries({ queryKey: ['households'] });
    },
  });
}

export function useRemoveHouseholdMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ householdId, userId }: { householdId: string; userId: string }) =>
      removeHouseholdMember(householdId, userId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['households', variables.householdId, 'members'] });
      queryClient.invalidateQueries({ queryKey: ['households'] });
    },
  });
}

export function useDeleteHousehold() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (householdId: string) => deleteHousehold(householdId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['households'] });
    },
  });
}

export function useRestoreHousehold() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (householdId: string) => restoreHousehold(householdId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['households'] });
    },
  });
}
