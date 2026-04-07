export interface AuthUser {
  username: string;
  email: string;
  token: string;
  is_admin?: boolean;
}

const TOKEN_KEY = "autoslice_token";
const USER_KEY  = "autoslice_user";

// saveAuth: if remember=true persist in localStorage (survives app restarts),
// otherwise use sessionStorage (cleared when app closes).
export function saveAuth(user: AuthUser, remember = false) {
  const store = remember ? localStorage : sessionStorage;
  // Clear the other store so stale tokens don't linger
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);

  store.setItem(TOKEN_KEY, user.token);
  store.setItem(USER_KEY, JSON.stringify({
    username: user.username,
    email: user.email,
    is_admin: user.is_admin ?? false,
  }));
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
}

function getStore(): Storage | null {
  if (typeof window === "undefined") return null;
  if (localStorage.getItem(TOKEN_KEY))  return localStorage;
  if (sessionStorage.getItem(TOKEN_KEY)) return sessionStorage;
  return null;
}

export function getToken(): string | null {
  return getStore()?.getItem(TOKEN_KEY) ?? null;
}

export function getUser(): { username: string; email: string; is_admin: boolean } | null {
  const raw = getStore()?.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function isLoggedIn(): boolean {
  return !!getToken();
}

export function isAdmin(): boolean {
  return !!getUser()?.is_admin;
}
