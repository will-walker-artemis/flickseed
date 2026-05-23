// "Auth" here is a polite fiction: there's no server. We pick a username
// (controls which JSON file you write to) and store a GitHub PAT in
// localStorage (used to call the Contents API).
//
// This is fine for a personal learning project on a public repo, but it is
// NOT secure against a malicious script running in your browser. Don't paste
// a PAT into a site you don't trust.

import { useSyncExternalStore } from 'react';

const USERNAME_KEY = 'flickseed:username';
const TOKEN_KEY = 'flickseed:gh_token';

export interface CurrentUser {
  username: string;
  token: string | null;
}

// useSyncExternalStore lets components re-render when localStorage changes
// (e.g. after saving on the Settings page). We notify via a small event bus.
const listeners = new Set<() => void>();
function emit() {
  for (const l of listeners) l();
}
function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}
function snapshot(): CurrentUser | null {
  const username = localStorage.getItem(USERNAME_KEY);
  if (!username) return null;
  return { username, token: localStorage.getItem(TOKEN_KEY) };
}

export function useCurrentUser(): CurrentUser | null {
  return useSyncExternalStore(subscribe, snapshot, () => null);
}

export function setCurrentUser(username: string, token: string) {
  localStorage.setItem(USERNAME_KEY, username);
  if (token) localStorage.setItem(TOKEN_KEY, token);
  emit();
}

export function signOut() {
  localStorage.removeItem(USERNAME_KEY);
  localStorage.removeItem(TOKEN_KEY);
  emit();
}
