export const API_BASE = ''; // Proxy handles /api via Vite

let accessToken = '';
let currentHouseholdId = '';

export function setApiToken(token: string) {
  accessToken = token;
}

export function setHouseholdId(id: string) {
  currentHouseholdId = id;
}

export function getHouseholdId() {
  return currentHouseholdId;
}

export function getHeaders() {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }
  if (currentHouseholdId) {
    headers['X-Household-Id'] = currentHouseholdId;
  }
  return headers;
}
