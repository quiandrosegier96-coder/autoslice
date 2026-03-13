export interface AuthUser {
  username: string;
  email: string;
  token: string;
  is_admin?: boolean;
}

export function saveAuth(user: AuthUser) {
  localStorage.setItem("autoslice_token", user.token);
  localStorage.setItem("autoslice_user", JSON.stringify({
    username: user.username,
    email: user.email,
    is_admin: user.is_admin ?? false,
  }));
}

export function clearAuth() {
  localStorage.removeItem("autoslice_token");
  localStorage.removeItem("autoslice_user");
}

export function getUser(): { username: string; email: string; is_admin: boolean } | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("autoslice_user");
  return raw ? JSON.parse(raw) : null;
}

export function isLoggedIn(): boolean {
  if (typeof window === "undefined") return false;
  return !!localStorage.getItem("autoslice_token");
}

const ADMIN_EMAILS = ["admin@autoslice.be", "admin2@autoslice.be"];

export function isAdmin(): boolean {
  const user = getUser();
  if (!user?.is_admin) return false;
  return ADMIN_EMAILS.includes(user.email);
}
